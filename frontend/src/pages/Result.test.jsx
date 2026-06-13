import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Result from "./Result.jsx";
import api from "../api/axios";

// Mock axios instance
vi.mock("../api/axios", () => ({
  default: {
    put: vi.fn(),
  },
}));

// Mock react-router-dom hooks
const mockNavigate = vi.fn();
let mockLocationState = null;

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ state: mockLocationState }),
}));

// Mock CaseTimeline component since it fetches data and contains internal timers/socket connections
vi.mock("../components/CaseTimeline", () => ({
  default: ({ caseId, theme }) => (
    <div data-testid="case-timeline">
      Timeline for {caseId} (Theme: {theme || "default"})
    </div>
  ),
}));

describe("Result Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocationState = null;
  });

  it("RESULT-FE-NO-STATE-001 @unit @regression renders fallback notice when no state is passed", () => {
    mockLocationState = null;
    render(<Result />);

    expect(screen.getByText("No dispatch result found.")).toBeInTheDocument();
    
    const returnBtn = screen.getByText("Return to Dispatch");
    expect(returnBtn).toBeInTheDocument();
    fireEvent.click(returnBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/dispatch");
  });

  it("RESULT-FE-NO-MATCH-001 @unit renders NoMatchView when no_match flag is true", () => {
    mockLocationState = {
      result: {
        no_match: true,
        no_match_reason: "missing_critical_equipment",
        rejected_hospitals: {
          missing_equipment: 3,
          insufficient_beds: 1,
          too_far: 2,
          total_evaluated: 6,
        },
      },
    };

    render(<Result />);

    expect(screen.getByText("No Eligible Hospital Found")).toBeInTheDocument();
    expect(screen.getByText("No hospital has the required equipment")).toBeInTheDocument();
    expect(screen.getByText("missing_critical_equipment")).toBeInTheDocument();
    expect(screen.getByText("Missing equipment")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("6 hospitals evaluated")).toBeInTheDocument();

    const returnBtn = screen.getByText("← NEW DISPATCH");
    fireEvent.click(returnBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/dispatch");
  });

  it("RESULT-FE-SUCCESS-001 @unit renders selected hospital and metrics successfully", () => {
    mockLocationState = {
      result: {
        case_id: 123,
        triage: {
          severity: "critical",
          condition: "cardiac_arrest",
        },
        selected_hospital: {
          hospital_id: 42,
          name: "City General Hospital",
          address: "123 Health Ave, Dehradun",
          distance_km: 4.5,
          eta_minutes: 12.0,
          available_beds: 5,
          score: 0.95,
          score_breakdown: {
            distance: 0.9,
            beds: 0.8,
            specialist: 1.0,
            equipment: 1.0,
            ml_confidence: 0.98,
          },
          pros: ["Highly equipped", "Cardiologist available"],
          cons: ["Moderate traffic"],
        },
      },
    };

    render(<Result />);

    // Renders header, brand, and action buttons
    expect(screen.getByText("MediRoute")).toBeInTheDocument();
    expect(screen.getByText("Premium Dispatch Result")).toBeInTheDocument();
    expect(screen.getByText("VIEW MAP →")).toBeInTheDocument();
    expect(screen.getByText("NEW DISPATCH")).toBeInTheDocument();

    // Renders selected hospital details
    expect(screen.getByText("City General Hospital")).toBeInTheDocument();
    expect(screen.getByText("123 Health Ave, Dehradun")).toBeInTheDocument();
    expect(screen.getByText("cardiac arrest")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();

    // Renders metrics
    expect(screen.getByText("4.5 km")).toBeInTheDocument();
    expect(screen.getByText("12 min")).toBeInTheDocument();
    expect(screen.getByText("5 beds")).toBeInTheDocument();

    // Renders pros / cons
    expect(screen.getByText("Highly equipped")).toBeInTheDocument();
    expect(screen.getByText("Cardiologist available")).toBeInTheDocument();
    expect(screen.getByText("Moderate traffic")).toBeInTheDocument();

    // Renders ML confidence
    expect(screen.getByText("ML Confidence")).toBeInTheDocument();
    expect(screen.getByText("98%")).toBeInTheDocument();

    // Timeline is rendered with theme="light"
    const timeline = screen.getByTestId("case-timeline");
    expect(timeline).toBeInTheDocument();
    expect(timeline.textContent).toContain("Timeline for 123 (Theme: light)");
  });

  it("RESULT-FE-OVERRIDE-001 @unit allows overriding the selected hospital", async () => {
    mockLocationState = {
      result: {
        case_id: 123,
        triage: {
          severity: "moderate",
          condition: "chest_pain",
        },
        selected_hospital: {
          hospital_id: 42,
          name: "City General Hospital",
          address: "123 Health Ave, Dehradun",
          distance_km: 4.5,
          eta_minutes: 12.0,
          available_beds: 5,
          score: 0.95,
        },
        alternatives: [
          {
            hospital_id: 99,
            name: "Alternative Trauma Center",
            address: "456 Safety Rd, Haridwar",
            distance_km: 8.2,
            eta_minutes: 20.0,
            available_beds: 8,
            score: 0.82,
            hospital_lat: 30.123,
            hospital_lng: 78.456,
          },
        ],
      },
    };

    api.put.mockResolvedValueOnce({ data: { status: "success" } });

    render(<Result />);

    expect(screen.getByText("Alternative Trauma Center")).toBeInTheDocument();
    expect(screen.getByText("8.2 km")).toBeInTheDocument();
    expect(screen.getByText("20 min")).toBeInTheDocument();
    expect(screen.getByText("8 beds")).toBeInTheDocument();

    const overrideBtn = screen.getByText("OVERRIDE");
    fireEvent.click(overrideBtn);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/cases/123/override-hospital", {
        new_hospital_id: 99,
        distance_km: 8.2,
        eta_minutes: 20.0,
        final_score: 0.82,
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith("/map", expect.any(Object));
  });
});
