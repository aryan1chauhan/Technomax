import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import CaseChat from "./CaseChat";
import api from "../api/axios";

vi.mock("../api/axios", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("CaseChat", () => {
  it("CASE-CHAT-FE-HISTORY-001 @api @integration renders message history when opened", async () => {
    api.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            case_id: 21,
            sender_id: 2,
            sender_role: "hospital",
            sender_email: "triage@test.com",
            body: "Prepare the red bay.",
            sent_at: "2026-04-26T10:00:00Z",
          },
        ],
      },
    });

    render(<CaseChat caseId={21} caseLabel="Case #21" socketEvent={null} />);

    expect(await screen.findByText("Prepare the red bay.")).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/api/cases/21/messages", { params: { limit: 50, page: 1 } });
  });

  it("CASE-CHAT-FE-SEND-001 @api @integration sending a message posts to the case endpoint", async () => {
    api.get.mockResolvedValueOnce({ data: { items: [] } });
    api.post.mockResolvedValueOnce({
      data: {
        id: 2,
        case_id: 21,
        sender_id: 5,
        sender_role: "ambulance",
        sender_email: "crew@test.com",
        body: "Patient is two minutes out.",
        sent_at: "2026-04-26T10:02:00Z",
      },
    });

    render(<CaseChat caseId={21} caseLabel="Case #21" socketEvent={null} />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("Type a message for the case team..."), {
      target: { value: "Patient is two minutes out." },
    });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/cases/21/messages", {
        body: "Patient is two minutes out.",
      });
    });
    expect(await screen.findByText("Patient is two minutes out.")).toBeInTheDocument();
  });
});
