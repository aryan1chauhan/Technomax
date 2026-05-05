import { describe, expect, it } from "vitest";
import {
  buildDispatchPayload,
  extractVitalsFromText,
  normalizeVitals,
} from "./Dispatch.jsx";

describe("Dispatch payload contract", () => {
  it("DISPATCH-FE-PAYLOAD-001 @unit @api @regression sends stabilize-first signals to backend", () => {
    const payload = buildDispatchPayload({
      selectedCondition: "respiratory",
      aiResult: {
        condition_label: "Respiratory Failure",
        critical_equipment: ["ventilator"],
        important_equipment: ["icu"],
        optional_equipment: ["lab"],
      },
      checkedEquipment: ["ventilator", "ventilator", "icu_equipment"],
      ambulanceEquipment: ["oxygen", "defibrillator"],
      vitals: { oxygen: "84", pulse: "142", systolic: "78", diastolic: "54" },
      selectedSeverity: 4,
      lat: 30.3165,
      lng: 78.0322,
      notes: "Patient deteriorating en route",
    });

    expect(payload).toMatchObject({
      condition: "respiratory",
      custom_condition: "Respiratory Failure",
      equipment_needed: ["ventilator", "icu_equipment"],
      required_equipment: ["ventilator", "icu_equipment"],
      critical_equipment: ["ventilator"],
      important_equipment: ["icu"],
      optional_equipment: ["lab"],
      ambulance_equipment: ["oxygen", "defibrillator"],
      vitals: { oxygen: 84, pulse: 142, systolic: 78, diastolic: 54 },
      ambulance_lat: 30.3165,
      ambulance_lng: 78.0322,
      severity: "critical",
      notes: "Patient deteriorating en route",
    });
  });

  it("DISPATCH-FE-VITALS-001 @unit ignores empty or malformed vitals deterministically", () => {
    expect(normalizeVitals({ oxygen: "", pulse: "abc", systolic: "91", diastolic: "" })).toEqual({
      systolic: 91,
    });
  });

  it("DISPATCH-FE-VITALS-002 @unit extracts common spoken vitals from voice transcript", () => {
    expect(
      extractVitalsFromText("SpO2 is 82, heart rate 138, blood pressure 76/40")
    ).toEqual({
      oxygen: "82",
      pulse: "138",
      systolic: "76",
      diastolic: "40",
    });
  });
});
