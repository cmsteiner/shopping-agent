import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows category input on the add form and submits the chosen category", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
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
            quantity: "1.000",
            unit: null,
            notes: "",
            category_id: 10,
            category_name: "Dairy",
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

    fireEvent.change(await screen.findByLabelText("Item name"), { target: { value: "Milk" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Add item" }));

    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/items", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        name: "Milk",
        quantity: "",
        category_id: "10",
        notes: ""
      })
    });
    await waitFor(() => {
      const dairyHeading = screen.getByRole("heading", { name: "Dairy" });
      expect(dairyHeading.closest(".category-card")).toHaveTextContent("Milk");
    });
  });

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
    expect(await screen.findByRole("heading", { name: "Dairy" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Produce" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Edit Milk" })).toBeInTheDocument();
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

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Edit Milk" })).toBeInTheDocument();
    });
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

  it("shows optimistic placeholders while a new item is being created", async () => {
    let resolveCreate;
    const createPromise = new Promise((resolve) => {
      resolveCreate = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
          categories: [],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockImplementationOnce(() => createPromise);
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.change(await screen.findByLabelText("Item name"), { target: { value: "Milk" } });
    fireEvent.click(screen.getByRole("button", { name: "Add item" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Edit Milk" })).toBeInTheDocument();
    });
    await waitFor(() => {
      const uncategorizedHeading = screen.getByRole("heading", { name: "Uncategorized" });
      expect(uncategorizedHeading.closest(".category-card")).toHaveTextContent("Milk");
    });
    expect(await screen.findByText("1")).toBeInTheDocument();
    expect(await screen.findByText("New")).toBeInTheDocument();

    resolveCreate({
      ok: true,
      json: async () => ({
        item: {
          id: 301,
          name: "Milk",
          quantity: "1.000",
          unit: null,
          notes: "",
          category_id: null,
          category_name: "Uncategorized",
          status: "ACTIVE",
          is_purchased: false,
          new_during_trip: true,
          version: 1,
          created_at: "2026-04-22T10:02:00Z",
          updated_at: "2026-04-22T10:02:00Z"
        },
        duplicate_check: { status: "clear" }
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

  it("shows duplicate validation after add and keeps the new item separate", async () => {
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
                  id: 88,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: "",
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
        status: 202,
        json: async () => ({
          pending_duplicate: {
            pending_confirmation_id: 17,
            pending_item: {
              id: 146,
              name: "Milk",
              quantity: "1",
              unit: null,
              notes: "2%",
              category_id: 10,
              category_name: "Dairy",
              status: "PENDING",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T10:05:00Z",
              updated_at: "2026-04-22T10:05:00Z"
            },
            existing_item: {
              id: 88,
              name: "Milk",
              quantity: "1",
              unit: null,
              notes: "",
              category_id: 10,
              category_name: "Dairy",
              status: "ACTIVE",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T10:00:00Z",
              updated_at: "2026-04-22T10:00:00Z"
            },
            options: ["merge", "keep_separate", "cancel"]
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          decision: "keep_separate",
          resolved_item: {
            id: 146,
            name: "Milk",
            quantity: "1",
            unit: null,
            notes: "2%",
            category_id: 10,
            category_name: "Dairy",
            status: "ACTIVE",
            is_purchased: false,
            new_during_trip: false,
            version: 2,
            created_at: "2026-04-22T10:05:00Z",
            updated_at: "2026-04-22T10:06:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.change(await screen.findByLabelText("Item name"), { target: { value: "Milk" } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "2%" } });
    fireEvent.click(screen.getByRole("button", { name: "Add item" }));

    expect(await screen.findByText("Possible duplicate item")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep separate" }));

    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Edit Milk" })).toHaveLength(2);
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/duplicates/17/resolve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({ decision: "keep_separate" })
    });
  });

  it("shows duplicate validation after add and can merge into the existing item", async () => {
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
                  id: 88,
                  name: "Milk",
                  quantity: "1",
                  unit: null,
                  notes: "",
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
        status: 202,
        json: async () => ({
          pending_duplicate: {
            pending_confirmation_id: 17,
            pending_item: {
              id: 146,
              name: "Milk",
              quantity: "1",
              unit: null,
              notes: "2%",
              category_id: 10,
              category_name: "Dairy",
              status: "PENDING",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T10:05:00Z",
              updated_at: "2026-04-22T10:05:00Z"
            },
            existing_item: {
              id: 88,
              name: "Milk",
              quantity: "1",
              unit: null,
              notes: "",
              category_id: 10,
              category_name: "Dairy",
              status: "ACTIVE",
              is_purchased: false,
              new_during_trip: false,
              version: 1,
              created_at: "2026-04-22T10:00:00Z",
              updated_at: "2026-04-22T10:00:00Z"
            },
            options: ["merge", "keep_separate", "cancel"]
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          decision: "merge",
          resolved_item: {
            id: 88,
            name: "Milk",
            quantity: "2.000",
            unit: null,
            notes: "2%",
            category_id: 10,
            category_name: "Dairy",
            status: "ACTIVE",
            is_purchased: false,
            new_during_trip: false,
            version: 2,
            created_at: "2026-04-22T10:00:00Z",
            updated_at: "2026-04-22T10:06:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.change(await screen.findByLabelText("Item name"), { target: { value: "Milk" } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "2%" } });
    fireEvent.click(screen.getByRole("button", { name: "Add item" }));

    expect(await screen.findByText("Possible duplicate item")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Merge items" }));

    await waitFor(() => {
      expect(screen.getByText("2.000")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/duplicates/17/resolve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({ decision: "merge" })
    });
  });

  it("creates a category from the category manager and adds it to the selectors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          category: { id: 20, name: "Bakery", sort_order: 20, version: 1 }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.change(await screen.findByLabelText("New category name"), { target: { value: "Bakery" } });
    fireEvent.click(screen.getByRole("button", { name: "Add category" }));

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Bakery" })).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/categories", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({ name: "Bakery" })
    });
  });

  it("deletes an empty category after confirmation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Delete category Dairy" }));
    expect(await screen.findByText("Delete category Dairy?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete Dairy" }));

    await waitFor(() => {
      expect(screen.queryByRole("option", { name: "Dairy" })).not.toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/categories/10", {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        base_version: 1,
        confirm: true
      })
    });
  });

  it("disables delete for a non-empty category and shows the move-items message", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({
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
                notes: "",
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
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    const button = await screen.findByRole("button", { name: "Delete category Dairy" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Move all items out of this category before deleting it.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("renames a category from the category manager and updates the selectors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          category: { id: 10, name: "Fresh Dairy", sort_order: 10, version: 2 },
          updated_item_count: 0
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Rename category Dairy" }));
    fireEvent.change(screen.getByLabelText("Rename category Dairy"), { target: { value: "Fresh Dairy" } });
    fireEvent.click(screen.getByRole("button", { name: "Save category Fresh Dairy" }));

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Fresh Dairy" })).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/categories/10", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        base_version: 1,
        name: "Fresh Dairy"
      })
    });
  });

  it("shows category conflict resolution after a stale rename and can overwrite with the user's changes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
          trip: null,
          categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
          items_by_category: [],
          pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
          server_time: "2026-04-22T10:00:00Z"
        })
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({
          error: {
            code: "version_conflict",
            message: "This category was updated before your changes were saved."
          },
          conflict: {
            entity_type: "category",
            entity_id: 10,
            server_version: 2,
            client_payload: {
              name: "Fresh Dairy"
            },
            server_payload: {
              id: 10,
              name: "Cold Storage",
              sort_order: 10,
              version: 2,
              updated_at: "2026-04-22T10:05:00Z"
            }
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          entity_type: "category",
          entity_id: 10,
          decision: "overwrite_with_client",
          category: {
            id: 10,
            name: "Fresh Dairy",
            sort_order: 10,
            version: 3
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Rename category Dairy" }));
    fireEvent.change(screen.getByLabelText("Rename category Dairy"), { target: { value: "Fresh Dairy" } });
    fireEvent.click(screen.getByRole("button", { name: "Save category Fresh Dairy" }));

    expect(await screen.findByText("Resolve category conflict")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep my category name" }));

    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Fresh Dairy" })).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/conflicts/resolve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        entity_type: "category",
        entity_id: 10,
        decision: "overwrite_with_client",
        server_version: 2,
        client_payload: {
          name: "Fresh Dairy"
        }
      })
    });
  });

  it("shows conflict resolution after a stale save and can overwrite with the user's changes", async () => {
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
                  notes: "",
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
        ok: false,
        status: 409,
        json: async () => ({
          error: {
            code: "version_conflict",
            message: "This item was updated before your changes were saved."
          },
          conflict: {
            entity_type: "item",
            entity_id: 101,
            server_version: 2,
            client_payload: {
              name: "Oat milk",
              quantity: "2",
              notes: "Unsweetened",
              category_id: 10
            },
            server_payload: {
              id: 101,
              name: "Milk",
              quantity: "1",
              notes: "",
              category_id: 10,
              category_name: "Dairy",
              is_purchased: false,
              new_during_trip: false,
              version: 2,
              updated_at: "2026-04-22T10:05:00Z"
            }
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          entity_type: "item",
          entity_id: 101,
          decision: "overwrite_with_client",
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
            version: 3,
            created_at: "2026-04-22T10:00:00Z",
            updated_at: "2026-04-22T10:06:00Z"
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<App token="dev-token" />);

    fireEvent.click(await screen.findByRole("button", { name: "Edit Milk" }));
    fireEvent.change(screen.getByLabelText("Name for Milk"), { target: { value: "Oat milk" } });
    fireEvent.change(screen.getByLabelText("Quantity for Milk"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Notes for Milk"), { target: { value: "Unsweetened" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Oat milk" }));

    expect(await screen.findByText("Resolve edit conflict")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep my changes" }));

    expect(await screen.findByText("Oat milk")).toBeInTheDocument();
    expect(await screen.findByText("Unsweetened")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/conflicts/resolve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": "dev-token"
      },
      body: JSON.stringify({
        entity_type: "item",
        entity_id: 101,
        decision: "overwrite_with_client",
        server_version: 2,
        client_payload: {
          name: "Oat milk",
          quantity: "2",
          notes: "Unsweetened",
          category_id: 10
        }
      })
    });
  });

  it("applies live item updates from the realtime stream", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
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
                notes: "",
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
    });
    const eventSources = [];
    class MockEventSource {
      constructor(url) {
        this.url = url;
        this.listeners = {};
        eventSources.push(this);
      }

      addEventListener(type, listener) {
        this.listeners[type] = listener;
      }

      close() {}
    }

    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", MockEventSource);

    render(<App token="dev-token" />);

    expect(await screen.findByText("Milk")).toBeInTheDocument();
    await waitFor(() => {
      expect(eventSources).toHaveLength(1);
    });
    expect(eventSources[0].url).toBe("/api/events/stream?token=dev-token&last_event_id=0");

    eventSources[0].listeners["item.updated"]({
      data: JSON.stringify({
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
      }),
      lastEventId: "5"
    });

    expect(await screen.findByText("Oat milk")).toBeInTheDocument();
    expect(await screen.findByText("Unsweetened")).toBeInTheDocument();
  });

  it("applies live category and trip events from the realtime stream", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
        trip: null,
        categories: [{ id: 10, name: "Dairy", sort_order: 10, version: 1 }],
        items_by_category: [],
        pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
        server_time: "2026-04-22T10:00:00Z"
      })
    });
    const eventSources = [];
    class MockEventSource {
      constructor(url) {
        this.url = url;
        this.listeners = {};
        eventSources.push(this);
      }

      addEventListener(type, listener) {
        this.listeners[type] = listener;
      }

      close() {}
    }

    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", MockEventSource);

    render(<App token="dev-token" />);

    await screen.findByText("Current List");
    await waitFor(() => {
      expect(eventSources).toHaveLength(1);
    });

    eventSources[0].listeners["category.updated"]({
      data: JSON.stringify({
        category: {
          id: 10,
          name: "Fresh Dairy",
          sort_order: 10,
          version: 2
        }
      }),
      lastEventId: "6"
    });
    eventSources[0].listeners["trip.started"]({
      data: JSON.stringify({
        trip: {
          id: 2,
          status: "ACTIVE",
          started_at: "2026-04-22T11:15:00Z",
          completed_at: null,
          version: 1
        }
      }),
      lastEventId: "7"
    });

    expect(await screen.findByRole("option", { name: "Fresh Dairy" })).toBeInTheDocument();
    expect(await screen.findByText("Shopping trip in progress")).toBeInTheDocument();
  });

  it("applies live list replacement and duplicate resolution events from the realtime stream", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        list: { id: 1, status: "ACTIVE", version: 1, created_at: "2026-04-22T10:00:00Z" },
        trip: { id: 2, status: "ACTIVE", started_at: "2026-04-22T11:15:00Z", completed_at: null, version: 1 },
        categories: [{ id: 10, name: "Bakery", sort_order: 10, version: 1 }],
        items_by_category: [],
        pending_prompts: { duplicate: null, conflict: null, trip_finish: null },
        server_time: "2026-04-22T10:00:00Z"
      })
    });
    const eventSources = [];
    class MockEventSource {
      constructor(url) {
        this.url = url;
        this.listeners = {};
        eventSources.push(this);
      }

      addEventListener(type, listener) {
        this.listeners[type] = listener;
      }

      close() {}
    }

    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", MockEventSource);

    render(<App token="dev-token" />);

    await screen.findByText("Current List");
    await waitFor(() => {
      expect(eventSources).toHaveLength(1);
    });

    eventSources[0].listeners["list.replaced"]({
      data: JSON.stringify({
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
        ]
      }),
      lastEventId: "8"
    });
    eventSources[0].listeners["trip.completed"]({
      data: JSON.stringify({
        trip: {
          id: 2,
          status: "COMPLETED",
          started_at: "2026-04-22T11:15:00Z",
          completed_at: "2026-04-22T12:00:00Z",
          version: 2
        }
      }),
      lastEventId: "9"
    });
    eventSources[0].listeners["item.duplicate_resolved"]({
      data: JSON.stringify({
        decision: "merge",
        resolved_item: {
          id: 201,
          name: "Bread",
          quantity: "2.000",
          unit: null,
          notes: "",
          category_id: 10,
          category_name: "Bakery",
          status: "ACTIVE",
          is_purchased: false,
          new_during_trip: false,
          version: 2,
          created_at: "2026-04-22T12:00:00Z",
          updated_at: "2026-04-22T12:01:00Z"
        }
      }),
      lastEventId: "10"
    });

    expect(await screen.findByText("Bread")).toBeInTheDocument();
    expect(await screen.findByText("2.000")).toBeInTheDocument();
    expect(screen.queryByText("Shopping trip in progress")).not.toBeInTheDocument();
  });
});
