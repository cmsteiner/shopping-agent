import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows an empty-state prompt when the list has no items", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
        trip: null,
        categories: [],
        items_by_category: [],
        pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
        server_time: "2026-04-22T10:00:00Z"
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Current List")).toBeInTheDocument();
    expect(await screen.findByText("Add your first item to get started.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/app-state", {
      headers: { "X-App-Token": "dev-token" }
    });
  });

  it("renders an active trip banner and grouped items from app-state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
        trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
        categories: [
          { id: 10, name: "Dairy", sort_order: 10, version: 1 },
          { id: 20, name: "Produce", sort_order: 20, version: 1 }
        ],
        items_by_category: [
          {
            category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
            items: [
              {
                id: 101,
                name: "Milk",
                quantity: "1",
                unit: null,
                notes: null,
                category_id: 10,
                category_name: "Dairy",
                status: "ACTIVE",
                is_purchased: false,
                new_during_trip: false,
                version: 1,
                created_at: "2026-04-22T10:00:00Z",
                updated_at: "2026-04-22T10:00:00Z"
              }
            ]
          },
          {
            category: { id: 20, name: "Produce", sort_order: 20, version: 1 },
            items: [
              {
                id: 102,
                name: "Apples",
                quantity: "6",
                unit: null,
                notes: "Honeycrisp",
                category_id: 20,
                category_name: "Produce",
                status: "ACTIVE",
                is_purchased: false,
                new_during_trip: true,
                version: 1,
                created_at: "2026-04-22T10:00:00Z",
                updated_at: "2026-04-22T10:00:00Z"
              }
            ]
          }
        ],
        pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
        server_time: "2026-04-22T10:00:00Z"
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Shopping trip in progress")).toBeInTheDocument();
    expect(await screen.findByText("Dairy")).toBeInTheDocument();
    expect(await screen.findByText("Produce")).toBeInTheDocument();
    expect(await screen.findByText("Milk")).toBeInTheDocument();
    expect(await screen.findByText("Apples")).toBeInTheDocument();
    expect(await screen.findByText("New")).toBeInTheDocument();
    expect(await screen.findByText("Honeycrisp")).toBeInTheDocument();
  });

  it("shows an error state when app-state fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    render(<App token="dev-token" />);

    await waitFor(() => {
      expect(screen.getByText("We couldn't load the shopping list.")).toBeInTheDocument();
    });
  });

  it("adds an item through the structured form and renders the new row", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item: {
            id: 301,
            name: "Milk",
            quantity: "1",
            unit: null,
            notes: "2%",
            category_id: null,
            category_name: "Uncategorized",
            status: "ACTIVE",
            is_purchased: false,
            new_during_trip: false,
            version: 1,
            created_at: "2026-04-22T10:02:00Z",
            updated_at: "2026-04-22T10:02:00Z"
          },
          duplicate_check: { status: "clear" }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Current List")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Milk" } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "2%" } });
    fireEvent.click(screen.getByRole("button", { name: "Add item" }));

    expect(await screen.findByText("Milk")).toBeInTheDocument();
    expect(await screen.findByText("2%")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/items", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        name: "Milk",
        quantity: "",
        category_id: "",
        notes: "2%"
      })
    });
  });

  it("toggles purchased state for an item", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [
            {
              category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: null,
                  category_id: 10,
                  category_name: "Dairy",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item: {
            id: 101,
            name: "Milk",
            quantity: "1",
            unit: null,
            notes: null,
            category_id: 10,
            category_name: "Dairy",
            status: "ACTIVE",
            is_purchased: true,
            new_during_trip: false,
            version: 2,
            created_at: "2026-04-22T10:00:00Z",
            updated_at: "2026-04-22T10:05:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    const checkbox = await screen.findByLabelText("Toggle Milk");
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(screen.getByText("Milk")).toHaveClass("purchased");
    });
  });

  it("deletes an item from the list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [
            {
              category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: null,
                  category_id: 10,
                  category_name: "Dairy",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Milk")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete Milk" }));

    await waitFor(() => {
      expect(screen.queryByText("Milk")).not.toBeInTheDocument();
    });
  });

  it("edits an item inline and saves the updated values", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [
            {
              category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: "2%",
                  category_id: 10,
                  category_name: "Dairy",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item: {
            id: 101,
            name: "Oat milk",
            quantity: "2",
            unit: null,
            notes: "Unsweetened",
            category_id: 10,
            category_name: "Dairy",
            status: "ACTIVE",
            is_purchased: false,
            new_during_trip: false,
            version: 2,
            created_at: "2026-04-22T10:00:00Z",
            updated_at: "2026-04-22T10:05:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Milk")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit Milk" }));
    fireEvent.change(screen.getByLabelText("Name for Milk"), { target: { value: "Oat milk" } });
    fireEvent.change(screen.getByLabelText("Quantity for Milk"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Notes for Milk"), { target: { value: "Unsweetened" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Oat milk" }));

    expect(await screen.findByText("Oat milk")).toBeInTheDocument();
    expect(await screen.findByText("Unsweetened")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/items/101", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        base_version: 1,
        name: "Oat milk",
        quantity: "2",
        notes: "Unsweetened",
        category_id: 10
      })
    });
  });

  it("reassigns an item to another category and moves it into that group", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [
            { id: 10, name: "Dairy", sort_order: 10, version: 1 },
            { id: 20, name: "Produce", sort_order: 20, version: 1 }
          ],
          items_by_category: [
            {
              category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: null,
                  category_id: 10,
                  category_name: "Dairy",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            },
            {
              category: { id: 20, name: "Produce", sort_order: 20, version: 1 },
              items: []
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item: {
            id: 101,
            name: "Milk",
            quantity: "1",
            unit: null,
            notes: null,
            category_id: 20,
            category_name: "Produce",
            status: "ACTIVE",
            is_purchased: false,
            new_during_trip: false,
            version: 2,
            created_at: "2026-04-22T10:00:00Z",
            updated_at: "2026-04-22T10:05:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Milk")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit Milk" }));
    fireEvent.change(screen.getByLabelText("Category for Milk"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Milk" }));

    await waitFor(() => {
      const produceHeading = screen.getByRole("heading", { name: "Produce" });
      expect(produceHeading.closest(".category-card")).toHaveTextContent("Milk");
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/items/101", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        base_version: 1,
        name: "Milk",
        quantity: "1",
        notes: "",
        category_id: 20
      })
    });
  });

  it("starts a shopping trip from the current list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [
            {
              category: { id: 10, name: "Dairy", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: null,
                  category_id: 10,
                  category_name: "Dairy",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          trip: {
            id: 2,
            status: "ACTIVE",
            started_at: "2026-04-22T11:15:00Z",
            completed_at: null,
            version: 1
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Start trip" }));

    expect(await screen.findByText("Shopping trip in progress")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/trips/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({})
    });
  });

  it("does not show the start-trip action when the list is empty", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
        trip: null,
        categories: [],
        items_by_category: [],
        pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
        server_time: "2026-04-22T10:00:00Z"
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Add your first item to get started.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start trip" })).not.toBeInTheDocument();
  });

  it("finishes a trip and carries an unchecked item onto the new list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
          categories: [{ id: 10, name: "Bakery", sort_order: 10, version: 1 }],
          items_by_category: [
            {
              category: { id: 10, name: "Bakery", sort_order: 10, version: 1 },
              items: [
                {
                  id: 101,
                  name: "Bread",
                  quantity: "1",
                  unit: null,
                  notes: "",
                  category_id: 10,
                  category_name: "Bakery",
                  status: "ACTIVE",
                  is_purchased: false,
                  new_during_trip: false,
                  version: 1,
                  created_at: "2026-04-22T10:00:00Z",
                  updated_at: "2026-04-22T10:00:00Z"
                }
              ]
            }
          ],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
          unchecked_items: [
            {
              id: 101,
              name: "Bread",
              quantity: "1",
              unit: null,
              notes: "",
              category_id: 10,
              category_name: "Bakery",
              status: "ACTIVE",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T10:00:00Z",
              updated_at: "2026-04-22T10:00:00Z"
            }
          ]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          archived_list: {
            id: 1,
            status: "ARCHIVED",
            archived_at: "2026-04-22T12:00:00Z"
          },
          new_active_list: {
            id: 3,
            status: "ACTIVE",
            version: 1,
            created_at: "2026-04-22T12:00:00Z"
          },
          carried_over_items: [
            {
              id: 201,
              name: "Bread",
              quantity: "1",
              unit: null,
              notes: "",
              category_id: 10,
              category_name: "Bakery",
              status: "ACTIVE",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T12:00:00Z",
              updated_at: "2026-04-22T12:00:00Z"
            }
          ],
          trip: {
            id: 2,
            status: "COMPLETED",
            started_at: "2026-04-22T11:15:00Z",
            completed_at: "2026-04-22T12:00:00Z",
            version: 2
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Finish trip" }));
    expect(await screen.findByText("Carry over unchecked items")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep Bread" }));

    await waitFor(() => {
      expect(screen.queryByText("Shopping trip in progress")).not.toBeInTheDocument();
    });
    expect(await screen.findByText("Bread")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/trips/2/finish/prepare", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({ base_version: 1 })
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/trips/2/finish/complete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        base_version: 1,
        carryover_items: [{ item_id: 101, carry_over: true }]
      })
    });
  });
});
