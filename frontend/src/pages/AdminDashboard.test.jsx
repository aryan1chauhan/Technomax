import { describe, expect, it } from "vitest";
import { calculateSimulatedScore } from "./AdminDashboard.jsx";

describe("Admin Dashboard ML Simulator Math", () => {
  it("ADMIN-FE-SIMULATION-001 @unit @validation verifies simulated score calculation for cardiac arrest", () => {
    // Setup inputs
    const inputs = {
      wSurvival: 0.22,
      wTreatment: 0.10,
      wEquipment: 0.13,
      wEta: 0.35,
      wLoad: 0.20,
      simCondition: "cardiac_arrest",
      simDistance: 12.4,
      simBeds: 15,
      simEquipment: {
        ventilator: true,
        defibrillator: true,
        ct_scan: false,
        blood_bank: true,
        icu: true
      },
      simSpecialists: {
        cardiology: true,
        neurology: false,
        trauma: true,
        respiratory: true
      }
    };

    // Calculate score
    const result = calculateSimulatedScore(inputs);

    // Verify properties exist
    expect(result).toHaveProperty("final");
    expect(result).toHaveProperty("breakdown");
    expect(result).toHaveProperty("weights");

    // Verify breakdown and weight totals
    expect(result.final).toBeGreaterThan(0);
    expect(result.final).toBeLessThanOrEqual(100);
    
    // Weights sum check (should be around 100%)
    const weightsSum = Object.values(result.weights).reduce((a, b) => a + b, 0);
    expect(weightsSum).toBeCloseTo(100, 0);
  });

  it("ADMIN-FE-SIMULATION-002 @unit @validation handles zero bed capacity scenario correctly", () => {
    const inputs = {
      wSurvival: 0.22,
      wTreatment: 0.10,
      wEquipment: 0.13,
      wEta: 0.35,
      wLoad: 0.20,
      simCondition: "stroke",
      simDistance: 5.0,
      simBeds: 0, // No beds
      simEquipment: { ventilator: true, defibrillator: true, ct_scan: true, blood_bank: true, icu: true },
      simSpecialists: { cardiology: true, neurology: true, trauma: true, respiratory: true }
    };

    const result = calculateSimulatedScore(inputs);
    // Load score contribution should be 0 since there are 0 available beds
    expect(result.breakdown.load).toBe(0);
  });
});
