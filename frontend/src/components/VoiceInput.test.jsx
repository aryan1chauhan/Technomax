import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import VoiceInput from "./VoiceInput";

class FakeSpeechRecognition {
  static instance = null;

  constructor() {
    this.continuous = false;
    this.interimResults = false;
    this.lang = "en-IN";
    this.onresult = null;
    this.onerror = null;
    this.onend = null;
    this.started = false;
    FakeSpeechRecognition.instance = this;
  }

  start() {
    this.started = true;
  }

  stop() {
    this.started = false;
    if (this.onend) this.onend();
  }

  emitFinal(transcript) {
    if (!this.onresult) return;
    this.onresult({
      results: [
        {
          0: { transcript },
          isFinal: true,
        },
      ],
    });
  }
}

function buildProps(overrides = {}) {
  return {
    analyzeVoiceText: vi.fn().mockResolvedValue({
      condition_label: "Respiratory",
      severity: 3,
      severity_label: "High",
      recommended_equipment: ["ventilator"],
      notes: "Stabilize airway",
      matched_condition_id: "respiratory",
    }),
    parseVoiceText: vi.fn().mockResolvedValue({
      severity: null,
      spo2: null,
      pulse: null,
      bp_systolic: null,
      bp_diastolic: null,
      confidence: {
        severity: 0,
        spo2: 0,
        pulse: 0,
        bp_systolic: 0,
        bp_diastolic: 0,
      },
    }),
    extractVitalsFromText: vi.fn().mockReturnValue({}),
    onApplyAnalysis: vi.fn(),
    isInternalNote: vi.fn().mockReturnValue(false),
    equipmentLabels: { ventilator: "Ventilator" },
    ...overrides,
  };
}

describe("VoiceInput", () => {
  beforeEach(() => {
    window.SpeechRecognition = FakeSpeechRecognition;
    window.webkitSpeechRecognition = FakeSpeechRecognition;
    localStorage.clear();
    FakeSpeechRecognition.instance = null;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("VOICE-FE-TOGGLE-001 @unit @validation toggles persistent mic mode with accessible button semantics", async () => {
    const props = buildProps();
    render(<VoiceInput {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Open voice input panel" }));

    const toggle = screen.getByRole("button", { name: "Turn microphone mode on" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    fireEvent.keyDown(toggle, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Turn microphone mode off" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByText("Listening...")).toBeInTheDocument();
      expect(localStorage.getItem("dispatch_voice_mode")).toBe("on");
    });

    fireEvent.click(screen.getByRole("button", { name: "Turn microphone mode off" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Turn microphone mode on" })).toHaveAttribute("aria-pressed", "false");
      expect(localStorage.getItem("dispatch_voice_mode")).toBe("off");
    });
  });

  it("VOICE-FE-CONFIDENCE-001 @unit @validation shows confirmed vs unconfirmed vitals from confidence threshold", async () => {
    const props = buildProps({
      parseVoiceText: vi.fn().mockResolvedValue({
        severity: null,
        spo2: 91,
        pulse: 130,
        bp_systolic: null,
        bp_diastolic: null,
        confidence: {
          severity: 0,
          spo2: 0.92,
          pulse: 0.42,
          bp_systolic: 0,
          bp_diastolic: 0,
        },
      }),
      extractVitalsFromText: vi.fn().mockReturnValue({ oxygen: "91", pulse: "130" }),
    });

    render(<VoiceInput {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Open voice input panel" }));
    fireEvent.click(screen.getByRole("button", { name: "Turn microphone mode on" }));

    await waitFor(() => expect(FakeSpeechRecognition.instance).not.toBeNull());
    await act(async () => {
      FakeSpeechRecognition.instance.emitFinal("SpO2 is 91 pulse around 130");
    });

    expect(await screen.findByText("SpO2 -> 91 Confirmed")).toBeInTheDocument();
    expect(await screen.findByText("Pulse -> 130 Unconfirmed")).toBeInTheDocument();
  });

  it("VOICE-FE-ERROR-001 @unit @adversarial renders explicit error state when speech cannot be parsed", async () => {
    const props = buildProps({
      analyzeVoiceText: vi.fn().mockResolvedValue(null),
      parseVoiceText: vi.fn().mockResolvedValue({
        severity: null,
        spo2: null,
        pulse: null,
        bp_systolic: null,
        bp_diastolic: null,
        confidence: {
          severity: 0,
          spo2: 0,
          pulse: 0,
          bp_systolic: 0,
          bp_diastolic: 0,
        },
      }),
      extractVitalsFromText: vi.fn().mockReturnValue({}),
    });

    render(<VoiceInput {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Open voice input panel" }));
    fireEvent.click(screen.getByRole("button", { name: "Turn microphone mode on" }));

    await waitFor(() => expect(FakeSpeechRecognition.instance).not.toBeNull());
    await act(async () => {
      FakeSpeechRecognition.instance.emitFinal("blurry audio static words");
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain("Speech was unintelligible or no vitals were detected. Please repeat clearly.");
  });
});
