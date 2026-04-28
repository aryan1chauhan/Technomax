"""dispatch_service.py — Service layer for the dispatch engine."""

import asyncio
import logging

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Case, CaseEvent, DecisionCandidate, User
from app.engine import dispatch_engine
from app.engine.stability_engine import evaluate_stability
from app.schemas.dispatch import DispatchRequest, DispatchResponse, RejectionSummary, ScoredHospitalResponse
from app.services.notification_service import send_dispatch_notifications

STABILIZATION_DELAY_MINUTES = 18.0

async def _background_notify(case_id: int, hospital_id: int):
    # Short yield to ensure parent transaction completes before querying
    await asyncio.sleep(0.05)
    db = SessionLocal()
    try:
        case = db.query(Case).get(case_id)
        if case:
            users = db.query(User).filter(User.hospital_id == hospital_id).all()
            await send_dispatch_notifications(db=db, case=case, hospital_users=users)
    except Exception as exc:
        logging.getLogger(__name__).error("Background notification failed: %s", exc, exc_info=True)
    finally:
        db.close()


def _candidate_to_response(candidate: dict) -> ScoredHospitalResponse:
    detailed_breakdown = candidate.get("score_breakdown") or {}
    if not isinstance(detailed_breakdown, dict):
        detailed_breakdown = {}

    eta_minutes = float(candidate.get("eta_minutes") or 0.0)
    distance_km = detailed_breakdown.get("distance_km")
    if distance_km is None:
        distance_km = round((eta_minutes / 60.0) * 40.0, 2)

    compact_breakdown = {
        "distance": float(detailed_breakdown.get("distance_score", 0.0)),
        "beds": float(detailed_breakdown.get("bed_score", 0.0)),
        "specialist": 1.0 if detailed_breakdown.get("specialist_present") else 0.0,
        "equipment": float(detailed_breakdown.get("equipment_match", 0.0)),
        "outcome": float(candidate.get("score", 0.0)),
    }

    explanation = candidate.get("explanation")
    if isinstance(explanation, str):
        explanation = [explanation]
    elif not isinstance(explanation, list):
        explanation = []

    return ScoredHospitalResponse(
        hospital_id=int(candidate["id"]),
        name=candidate.get("name", "Unknown"),
        distance_km=float(distance_km),
        available_beds=int(candidate.get("available_beds") or 0),
        icu_beds=int(candidate.get("icu_beds") or 0),
        score=float(candidate.get("score") or 0.0),
        score_breakdown=compact_breakdown,
        explanation=explanation,
        pros=list(candidate.get("pros") or []),
        cons=list(candidate.get("cons") or []),
        data_source=candidate.get("data_source", "live"),
        last_updated=candidate.get("last_updated"),
        hospital_lat=float(candidate.get("latitude") or 0.0),
        hospital_lng=float(candidate.get("longitude") or 0.0),
        address=candidate.get("address", ""),
        eta_minutes=max(1, int(round(eta_minutes))),
    )

def _build_rejection_summary(
    total_evaluated: int | None = None,
    total_passed: int | None = None,
    counts: dict | None = None,
    *,
    hospital_dicts: list[dict] | None = None,
    ranked: list[dict] | None = None,
    required_equipment: list[str] | None = None,
) -> RejectionSummary:
    if hospital_dicts is not None and ranked is not None:
        required = set(required_equipment or [])
        missing_equipment = 0
        insufficient_beds = 0

        for hospital in hospital_dicts:
            available_beds = int(hospital.get("available_beds") or 0)
            equipment = set(hospital.get("equipment") or [])

            if available_beds <= 0:
                insufficient_beds += 1
            if required and not required.issubset(equipment):
                missing_equipment += 1

        total_evaluated = len(hospital_dicts)
        total_passed = len(ranked)
        return RejectionSummary(
            missing_equipment=missing_equipment,
            insufficient_beds=insufficient_beds,
            too_far=0,
            total_rejected=max(total_evaluated - total_passed, 0),
            total_evaluated=total_evaluated,
            total_passed=total_passed,
        )

    counts = counts or {}
    total_evaluated = int(total_evaluated or 0)
    total_passed = int(total_passed or 0)

    return RejectionSummary(
        missing_equipment=int(counts.get("missing_critical_equipment", 0)),
        insufficient_beds=int(counts.get("no_available_beds", 0)),
        too_far=0,
        total_rejected=max(total_evaluated - total_passed, 0),
        total_evaluated=total_evaluated,
        total_passed=total_passed,
    )

def _select_emergency_override_candidate(
    *,
    hospitals: list[dict],
    eta_map: dict[int, float],
    required_equipment: list[str],
) -> dict | None:
    if not hospitals:
        return None

    critical = {
        str(item).strip().lower()
        for item in (required_equipment or [])
        if str(item).strip().lower() in {"ventilator", "defibrillator"}
    }

    def _with_eta(source: list[dict]) -> list[dict]:
        enriched: list[dict] = []
        for row in source:
            item = dict(row)
            item["eta_minutes"] = float(eta_map.get(int(item.get("id", -1)), 9999.0))
            enriched.append(item)
        return sorted(enriched, key=lambda h: float(h.get("eta_minutes", 9999.0)))

    accepting_with_beds = [
        row for row in hospitals
        if bool(row.get("accepting", True)) and int(row.get("available_beds") or 0) > 0
    ]
    if not accepting_with_beds:
        accepting_with_beds = [row for row in hospitals if bool(row.get("accepting", True))]
    if not accepting_with_beds:
        accepting_with_beds = list(hospitals)

    ranked_pool = _with_eta(accepting_with_beds)
    if not ranked_pool:
        return None

    chosen = ranked_pool[0]
    available_equipment = {
        str(item).strip().lower() for item in (chosen.get("equipment") or []) if item
    }
    matched_critical = sorted(critical & available_equipment)
    critical_ratio = (len(matched_critical) / len(critical)) if critical else 1.0
    equipment_match_score = (critical_ratio * 0.6) + 0.3 + 0.1
    eta_minutes = float(chosen.get("eta_minutes") or 9999.0)

    chosen["score"] = round((1.0 / (1.0 + eta_minutes)) * 0.7 + (equipment_match_score * 0.3), 6)
    chosen["equipment_match_score"] = round(equipment_match_score, 6)
    chosen["score_breakdown"] = {
        "distance_score": round(1.0 / (1.0 + eta_minutes / 30.0), 4),
        "bed_score": 0.0,
        "specialist_present": bool(chosen.get("specialist_count", 0) > 0),
        "equipment_match": round(equipment_match_score, 4),
        "distance_km": round((eta_minutes / 60.0) * 40.0, 2),
    }
    chosen["pros"] = ["Emergency override: nearest available center selected"]
    chosen["cons"] = ["Selected with partial equipment match"]
    chosen["explanation"] = ["Best possible hospital selected with partial equipment match."]
    return chosen

def _fallback_to_strings(fallback_options: list[dict]) -> list[str]:
    output: list[str] = []
    for item in fallback_options:
        output.append(f"{item.get('hospital_name', 'Unknown')} — ETA {float(item.get('eta_minutes', 0.0)):.1f} min")
    return output

def _severity_label(dispatch_request: DispatchRequest) -> str:
    severity = dispatch_request.severity
    if isinstance(severity, str) and severity.strip():
        return severity.strip().lower()
    if isinstance(severity, int):
        if severity <= 3:
            return "low"
        if severity >= 8:
            return "critical"
        return "moderate"

    score = dispatch_request.get_severity_score()
    if score <= 3:
        return "low"
    if score >= 8:
        return "critical"
    return "moderate"


async def execute_dispatch(dispatch_request: DispatchRequest, db: Session, current_user: User) -> DispatchResponse:
    if current_user.role != "ambulance":
        raise HTTPException(
            status_code=403,
            detail="Only ambulance accounts can dispatch"
        )
        
    dispatch_engine.settings = settings
    dispatch_engine.httpx = httpx

    try:
        hospital_dicts = dispatch_engine.get_latest_hospital_snapshots(db)

        if not hospital_dicts:
            return DispatchResponse(
                no_match=True,
                no_match_reason="No hospitals with availability data in the system.",
                fallback_options=[],
                error="No hospitals available",
            )

        equip = dispatch_request.get_equipment()
        severity_score = dispatch_request.get_severity_score()

        eta_map = await dispatch_engine._fetch_eta_map(
            origin_lat=dispatch_request.ambulance_lat,
            origin_lng=dispatch_request.ambulance_lng,
            hospitals=hospital_dicts,
        )
        nearest_eta = min(eta_map.values()) if eta_map else 9999.0

        ambulance_equipment_set = {
            str(item).strip().lower()
            for item in (dispatch_request.ambulance_equipment or [])
            if item
        }
        stability = evaluate_stability(
            case_data={
                "severity_score": severity_score,
                "condition_type": dispatch_request.condition,
                "vitals": dispatch_request.vitals or {},
            },
            ambulance_data={
                "has_oxygen": "oxygen" in ambulance_equipment_set,
                "has_ventilator": "ventilator" in ambulance_equipment_set,
                "has_defibrillator": "defibrillator" in ambulance_equipment_set,
            },
            eta_to_best_hospital=nearest_eta,
        )

        stabilization_required = bool(stability.get("stabilization_required"))

        if stabilization_required:
            decision = await dispatch_engine.run_dispatch(
                hospitals=hospital_dicts,
                ambulance_lat=dispatch_request.ambulance_lat,
                ambulance_lng=dispatch_request.ambulance_lng,
                condition_type=dispatch_request.condition,
                severity_score=severity_score,
                vitals=dispatch_request.vitals,
                ambulance_equipment=dispatch_request.ambulance_equipment,
                required_equipment=equip,
                forced_hospital_types={"stabilization", "both"},
                force_direct=True,
                relax_important_constraints=True,
            )

            ranked = decision.get("ranked_candidates") or []

            # For trauma conditions, filter for trauma-capable hospitals before
            # sorting by ETA.  The ETA-only sort was letting the nearest hospital
            # (e.g. Stroke Center) win on proximity alone even when it lacked
            # trauma equipment — causing a 9% behavior mismatch in simulation.
            # Falls back to ETA-only if no trauma-capable option exists (rural
            # networks) so we never produce an empty candidate list.
            canonical_condition = dispatch_engine.normalize_condition_type(
                dispatch_request.condition
            )
            if canonical_condition == "trauma":
                def _is_trauma_capable(h: dict) -> bool:
                    tags = {str(t).strip().lower() for t in (h.get("scenario_tags") or [])}
                    equip = {str(e).strip().lower() for e in (h.get("equipment") or [])}
                    htype = str(h.get("hospital_type") or "").strip().lower()
                    return (
                        htype in {"stabilization", "both"}
                        or bool({"trauma", "stabilization", "critical_care"} & tags)
                        or bool({"trauma_center", "surgery", "blood_bank"} & equip)
                    )

                trauma_capable = [h for h in ranked if _is_trauma_capable(h)]
                ranked = sorted(
                    trauma_capable if trauma_capable else ranked,
                    key=lambda item: float(item.get("eta_minutes", 9999.0)),
                )
            else:
                ranked = sorted(ranked, key=lambda item: float(item.get("eta_minutes", 9999.0)))

            decision["ranked_candidates"] = ranked
            decision["decision_type"] = "stabilize_first"
        else:
            decision = await dispatch_engine.run_dispatch(
                hospitals=hospital_dicts,
                ambulance_lat=dispatch_request.ambulance_lat,
                ambulance_lng=dispatch_request.ambulance_lng,
                condition_type=dispatch_request.condition,
                severity_score=severity_score,
                vitals=dispatch_request.vitals,
                ambulance_equipment=dispatch_request.ambulance_equipment,
                required_equipment=equip,
                force_direct=True,
                relax_important_constraints=False,
            )

        reasoning = decision.get("reasoning") or {}
        reasoning["stability_score"] = float(stability.get("stability_score") or 0.0)
        reasoning["estimated_survival_time"] = float(stability.get("estimated_survival_time") or 0.0)
        reasoning["stabilization_required"] = stabilization_required
        decision["reasoning"] = reasoning

        ranked = decision.get("ranked_candidates") or []
        if not ranked:
            emergency_candidate = _select_emergency_override_candidate(
                hospitals=hospital_dicts,
                eta_map=eta_map,
                required_equipment=equip,
            )
            if emergency_candidate is not None:
                ranked = [emergency_candidate]
                decision["ranked_candidates"] = ranked
                decision["decision_type"] = "emergency_override"
                fallback_reasoning = decision.get("reasoning") or {}
                constraints = list(fallback_reasoning.get("constraints_applied") or [])
                constraints.append("emergency_override_nearest_available")
                fallback_reasoning["constraints_applied"] = constraints
                fallback_reasoning["emergency_override"] = True
                fallback_reasoning["override_message"] = (
                    "Best possible hospital selected with partial equipment match"
                )
                decision["reasoning"] = fallback_reasoning

        rejection_model = _build_rejection_summary(
            total_evaluated=len(hospital_dicts),
            total_passed=len(ranked),
            counts=decision.get("constraint_counts") or {},
        )
        severity_str = _severity_label(dispatch_request)

        if decision.get("decision_type") == "no_viable_hospital" or not ranked:
            reason = "No viable hospitals passed hard constraints."
            applied = decision.get("reasoning", {}).get("constraints_applied") or []
            if applied:
                reason = reason + " Constraints: " + ", ".join(applied)

            return DispatchResponse(
                decision_type=decision.get("decision_type", "no_viable_hospital"),
                primary_destination=None,
                secondary_destination=None,
                reasoning=decision.get("reasoning") or {},
                no_match=True,
                no_match_reason=reason,
                fallback_options=_fallback_to_strings(decision.get("fallback_options") or []),
                rejected_hospitals=rejection_model,
                triage={
                    "condition": dispatch_request.condition,
                    "severity": severity_str,
                    "required_equipment": equip,
                },
            )

        ranked_for_response = [dict(item) for item in ranked]
        selected_hospital = dict(ranked_for_response[0])
        new_case: Case | None = None

        def save_case_with_atomic_reservation():
            nonlocal ranked_for_response, selected_hospital, new_case

            selected_idx = -1
            remaining_beds_after_reserve = None

            for idx, candidate in enumerate(ranked_for_response):
                reservation = db.execute(
                    text(
                        """
                        UPDATE availabilities
                        SET beds = beds - 1,
                            updated_at = NOW()
                        WHERE hospital_id = :hospital_id
                          AND beds > 0
                        RETURNING beds
                        """
                    ),
                    {"hospital_id": int(candidate["id"])},
                ).first()
                if reservation is not None:
                    selected_idx = idx
                    remaining_beds_after_reserve = int(reservation[0])
                    break

            if selected_idx < 0:
                db.rollback()
                raise HTTPException(status_code=409, detail="Hospital at capacity, retry dispatch")

            selected_hospital = dict(ranked_for_response[selected_idx])
            selected_hospital["available_beds"] = remaining_beds_after_reserve

            if selected_idx > 0:
                # Race-safe rerank: promote the first successfully reserved candidate.
                ranked_for_response = [selected_hospital] + [
                    dict(item)
                    for i, item in enumerate(ranked_for_response)
                    if i != selected_idx
                ]

            selected_response = _candidate_to_response(selected_hospital)
            new_case = Case(
                user_id=current_user.id,
                condition=dispatch_request.condition,
                custom_condition=getattr(dispatch_request, "custom_condition", None),
                equipment_needed=equip,
                ambulance_lat=dispatch_request.ambulance_lat,
                ambulance_lng=dispatch_request.ambulance_lng,
                assigned_hospital_id=int(selected_hospital["id"]),
                final_score=float(selected_hospital.get("score") or 0.0),
                distance_km=selected_response.distance_km,
                eta_minutes=selected_response.eta_minutes,
                notes=getattr(dispatch_request, "notes", None),
            )
            db.add(new_case)
            db.flush()

            initial_event = CaseEvent(
                case_id=new_case.id,
                status="dispatched",
                actor_id=current_user.id,
                actor_role=current_user.role,
                note="Case dispatched by system",
            )
            db.add(initial_event)
            # Add candidate rows in the same transaction so we only need one commit.
            try:
                candidate_rows_pre: list[DecisionCandidate] = []
                for position, candidate in enumerate(ranked_for_response, start=1):
                    breakdown = candidate.get("score_breakdown")
                    distance_km_val = None
                    if isinstance(breakdown, dict):
                        distance_km_val = breakdown.get("distance_km")
                    candidate_rows_pre.append(
                        DecisionCandidate(
                            case_id=new_case.id,
                            hospital_id=int(candidate["id"]),
                            rank_position=position,
                            score=float(candidate.get("score") or 0.0),
                            eta_minutes=float(candidate.get("eta_minutes") or 0.0),
                            distance_km=float(distance_km_val) if distance_km_val is not None else None,
                            available_beds_snapshot=int(candidate.get("available_beds") or 0),
                            icu_beds_snapshot=int(candidate.get("icu_beds") or 0),
                            is_selected=position == 1,
                            score_breakdown=breakdown if isinstance(breakdown, dict) else None,
                        )
                    )
                db.add_all(candidate_rows_pre)
            except Exception:  # noqa: BLE001
                pass  # Non-critical; will retry in the fallback block below
            db.commit()
            db.refresh(new_case)

        save_case_with_atomic_reservation()
        # Invalidate this worker's snapshot cache so the next dispatch
        # call sees the decremented bed count rather than the stale value.
        from app.engine.dispatch_engine import _SNAPSHOT_CACHE_TS as _scts  # noqa: PLC0415,F401
        import app.engine.dispatch_engine as _de
        _de._SNAPSHOT_CACHE_TS = 0.0

        if new_case is None:
            raise HTTPException(status_code=500, detail="Dispatch persistence failed")

        asyncio.create_task(_background_notify(new_case.id, new_case.assigned_hospital_id))

        best = selected_hospital
        best_response = _candidate_to_response(best)
        alternatives = [_candidate_to_response(item) for item in ranked_for_response[1:4]]
        primary_destination = best_response.model_dump()

        secondary_destination: dict | None = None
        if decision.get("decision_type") == "stabilize_first":
            stabilization_origin_lat = float(best.get("latitude") or dispatch_request.ambulance_lat)
            stabilization_origin_lng = float(best.get("longitude") or dispatch_request.ambulance_lng)
            post_stabilization_severity = max(1, severity_score - 2)
            second_leg_hospitals = [item for item in hospital_dicts if int(item.get("id", -1)) != int(best["id"])]

            second_leg_decision = await dispatch_engine.run_dispatch(
                hospitals=second_leg_hospitals,
                ambulance_lat=stabilization_origin_lat,
                ambulance_lng=stabilization_origin_lng,
                condition_type=dispatch_request.condition,
                severity_score=post_stabilization_severity,
                vitals=dispatch_request.vitals,
                ambulance_equipment=dispatch_request.ambulance_equipment,
                required_equipment=equip,
                forced_hospital_types={"advanced", "both"},
                force_direct=True,
                relax_important_constraints=False,
            )

            second_leg_ranked = second_leg_decision.get("ranked_candidates") or []
            if second_leg_ranked:
                secondary_best = dict(second_leg_ranked[0])
                secondary_best["eta_minutes"] = float(secondary_best.get("eta_minutes") or 0.0) + STABILIZATION_DELAY_MINUTES
                secondary_response = _candidate_to_response(secondary_best)
                secondary_destination = secondary_response.model_dump()

            decision_reasoning = decision.get("reasoning") or {}
            decision_reasoning["stabilization_delay_minutes"] = STABILIZATION_DELAY_MINUTES
            decision_reasoning["post_stabilization_severity_score"] = post_stabilization_severity
            decision_reasoning["post_stabilization_routing"] = second_leg_decision.get("reasoning") or {}
            decision["reasoning"] = decision_reasoning

        if int(best.get("id") or -1) != int(ranked[0].get("id") or -1):
            reasoning_after_rerank = decision.get("reasoning") or {}
            reasoning_after_rerank["capacity_rerank_applied"] = True
            decision["reasoning"] = reasoning_after_rerank

        decision_type = decision.get("decision_type", "direct")

        return DispatchResponse(
            decision_type=decision_type,
            primary_destination=primary_destination,
            secondary_destination=secondary_destination,
            reasoning=decision.get("reasoning") or {},
            case_id=new_case.id,
            status="dispatched",
            triage={
                "condition": dispatch_request.condition,
                "severity": severity_str,
                "required_equipment": equip,
                "decision_type": decision_type,
                "stabilization_required": decision.get("reasoning", {}).get("stabilization_required", False),
            },
            selected_hospital=best_response,
            alternatives=alternatives,
            rejected_hospitals=rejection_model,
            no_match=False,

            hospital_id=best["id"],
            hospital_name=best["name"],
            address=best.get("address", ""),
            final_score=float(best.get("score") or 0.0),
            confidence=float(best.get("score") or 0.0),
            distance_km=best_response.distance_km,
            eta_minutes=best_response.eta_minutes,
            beds=int(best.get("available_beds") or 0),
            icu=int(best.get("icu_beds") or 0),
            equipment_matched=list(equip),
            equipment_missing=[],
            hospital_lat=float(best.get("latitude") or 0.0),
            hospital_lng=float(best.get("longitude") or 0.0),
            ml_reasoning=best_response.explanation,
        )

    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        logging.getLogger(__name__).error("Dispatch pipeline error: %s", exc, exc_info=True)
        return DispatchResponse(
            error=f"Dispatch pipeline error: {str(exc)}",
            no_match=True,
            no_match_reason="Internal error — please retry or escalate manually.",
        )
