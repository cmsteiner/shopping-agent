import { useEffect, useState } from "react";

const initialState = {
  status: "loading",
  data: null
};

function formatStartTime(isoString) {
  if (!isoString) {
    return "";
  }
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function upsertItemIntoGroups(groups, item) {
  const nextGroups = groups.map((group) => ({
    ...group,
    items: group.items.filter((existing) => existing.id !== item.id)
  }));
  const categoryName = item.category_name || "Uncategorized";
  const categoryId = item.category_id ?? null;
  const existingGroup = nextGroups.find(
    (group) => (group.category.id ?? null) === categoryId && group.category.name === categoryName
  );

  if (existingGroup) {
    existingGroup.items = [...existingGroup.items, item];
    return nextGroups;
  }

  return [
    ...nextGroups,
    {
      category: {
        id: categoryId,
        name: categoryName,
        sort_order: 999999,
        version: 1
      },
      items: [item]
    }
  ];
}

function removeItemFromGroups(groups, itemId) {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.id !== itemId)
    }))
    .filter((group) => group.items.length > 0);
}

function buildGroupsFromItems(categories, items) {
  const groupedMap = new Map();
  const orderedGroups = [];

  for (const category of categories) {
    const key = String(category.id ?? "uncategorized");
    const group = {
      category,
      items: []
    };
    groupedMap.set(key, group);
    orderedGroups.push(group);
  }

  for (const item of items) {
    const categoryId = item.category_id ?? null;
    const key = String(categoryId ?? "uncategorized");
    if (!groupedMap.has(key)) {
      const fallbackGroup = {
        category: {
          id: categoryId,
          name: item.category_name || "Uncategorized",
          sort_order: 999999,
          version: 1
        },
        items: []
      };
      groupedMap.set(key, fallbackGroup);
      orderedGroups.push(fallbackGroup);
    }
    groupedMap.get(key).items.push(item);
  }

  return orderedGroups.filter((group) => group.items.length > 0);
}

export default function App({ token }) {
  const [state, setState] = useState(initialState);
  const [form, setForm] = useState({
    name: "",
    quantity: "",
    category_id: "",
    notes: ""
  });
  const [editingItemId, setEditingItemId] = useState(null);
  const [editForm, setEditForm] = useState({
    name: "",
    quantity: "",
    category_id: "",
    notes: ""
  });
  const [tripReview, setTripReview] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadAppState() {
      try {
        const response = await fetch("/api/app-state", {
          headers: { "X-App-Token": token }
        });
        if (!response.ok) {
          throw new Error(`Failed to load app-state: ${response.status}`);
        }
        const data = await response.json();
        if (!cancelled) {
          setState({ status: "ready", data });
        }
      } catch (error) {
        if (!cancelled) {
          setState({ status: "error", data: null });
        }
      }
    }

    loadAppState();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state.status === "loading") {
    return <main className="app-shell">Loading…</main>;
  }

  if (state.status === "error") {
    return (
      <main className="app-shell">
        <section className="error-panel">
          <h1>Current List</h1>
          <p>We couldn&apos;t load the shopping list.</p>
        </section>
      </main>
    );
  }

  const { data } = state;
  const hasItems = data.items_by_category.length > 0;

  async function handleAddItem(event) {
    event.preventDefault();
    const response = await fetch("/api/items", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify(form)
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
      }
    }));
    setForm({ name: "", quantity: "", category_id: "", notes: "" });
  }

  async function handleToggleItem(item) {
    const response = await fetch(`/api/items/${item.id}/toggle-purchased`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: item.version,
        is_purchased: !item.is_purchased
      })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
      }
    }));
  }

  function startEditingItem(item) {
    setEditingItemId(item.id);
    setEditForm({
      name: item.name ?? "",
      quantity: item.quantity ?? "",
      category_id: item.category_id == null ? "" : String(item.category_id),
      notes: item.notes ?? ""
    });
  }

  async function handleSaveItem(item) {
    const categoryId = editForm.category_id === "" ? null : Number(editForm.category_id);
    const response = await fetch(`/api/items/${item.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: item.version,
        name: editForm.name,
        quantity: editForm.quantity,
        notes: editForm.notes,
        category_id: categoryId
      })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
      }
    }));
    setEditingItemId(null);
  }

  async function handleDeleteItem(item) {
    const response = await fetch(`/api/items/${item.id}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({ base_version: item.version })
    });
    if (!response.ok) {
      return;
    }
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: removeItemFromGroups(current.data.items_by_category, item.id)
      }
    }));
  }

  async function handleStartTrip() {
    const response = await fetch("/api/trips/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({})
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        trip: payload.trip
      }
    }));
  }

  async function handleFinishTrip() {
    if (!data.trip) {
      return;
    }
    const response = await fetch(`/api/trips/${data.trip.id}/finish/prepare`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({ base_version: data.trip.version })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setTripReview({
      trip: payload.trip,
      uncheckedItems: payload.unchecked_items
    });
  }

  async function handleTripCarryoverDecision(item, carryOver) {
    if (!tripReview?.trip) {
      return;
    }
    const response = await fetch(`/api/trips/${tripReview.trip.id}/finish/complete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: tripReview.trip.version,
        carryover_items: [{ item_id: item.id, carry_over: carryOver }]
      })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        list: payload.new_active_list,
        trip: null,
        items_by_category: buildGroupsFromItems(current.data.categories, payload.carried_over_items)
      }
    }));
    setTripReview(null);
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Shared household list</p>
        <h1>Current List</h1>
      </header>

      {!data.trip && hasItems ? (
        <section className="trip-actions">
          <button className="primary-button" onClick={handleStartTrip} type="button">
            Start trip
          </button>
        </section>
      ) : null}

      {data.trip ? (
        <>
          <section className="trip-banner">
            <strong>Shopping trip in progress</strong>
            <span>Started at {formatStartTime(data.trip.started_at)}</span>
          </section>
          <section className="trip-actions">
            <button className="primary-button" onClick={handleFinishTrip} type="button">
              Finish trip
            </button>
          </section>
        </>
      ) : null}

      {tripReview ? (
        <section className="trip-review-panel">
          <h2>Carry over unchecked items</h2>
          {tripReview.uncheckedItems.map((item) => (
            <div className="trip-review-row" key={item.id}>
              <span>{item.name}</span>
              <div className="trip-review-actions">
                <button className="primary-button" onClick={() => handleTripCarryoverDecision(item, true)} type="button">
                  Keep {item.name}
                </button>
                <button className="ghost-button" onClick={() => handleTripCarryoverDecision(item, false)} type="button">
                  Skip {item.name}
                </button>
              </div>
            </div>
          ))}
        </section>
      ) : null}

      <section className="add-panel">
        <form className="add-form" onSubmit={handleAddItem}>
          <label>
            <span>Item name</span>
            <input
              name="name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label>
            <span>Quantity</span>
            <input
              name="quantity"
              value={form.quantity}
              onChange={(event) => setForm((current) => ({ ...current, quantity: event.target.value }))}
            />
          </label>
          <label>
            <span>Notes</span>
            <input
              name="notes"
              value={form.notes}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
          </label>
          <button className="primary-button" type="submit" disabled={!form.name.trim()}>
            Add item
          </button>
        </form>
      </section>

      {!hasItems ? (
        <section className="empty-state">
          <h2>No items yet</h2>
          <p>Add your first item to get started.</p>
        </section>
      ) : (
        <section className="category-list">
          {data.items_by_category.map((group) => (
            <article className="category-card" key={group.category.id ?? group.category.name}>
              <h2>{group.category.name}</h2>
              <ul>
                {group.items.map((item) => (
                  <li className="item-row" key={item.id}>
                    <div className="item-main">
                      <label className="check-toggle">
                        <input
                          aria-label={`Toggle ${item.name}`}
                          checked={item.is_purchased}
                          onChange={() => handleToggleItem(item)}
                          type="checkbox"
                        />
                      </label>
                      {editingItemId === item.id ? (
                        <div className="item-edit-fields">
                          <label>
                            <span>Name for {item.name}</span>
                            <input
                              aria-label={`Name for ${item.name}`}
                              value={editForm.name}
                              onChange={(event) =>
                                setEditForm((current) => ({ ...current, name: event.target.value }))
                              }
                            />
                          </label>
                          <label>
                            <span>Quantity for {item.name}</span>
                            <input
                              aria-label={`Quantity for ${item.name}`}
                              value={editForm.quantity}
                              onChange={(event) =>
                                setEditForm((current) => ({ ...current, quantity: event.target.value }))
                              }
                            />
                          </label>
                          <label>
                            <span>Category for {item.name}</span>
                            <select
                              aria-label={`Category for ${item.name}`}
                              value={editForm.category_id}
                              onChange={(event) =>
                                setEditForm((current) => ({ ...current, category_id: event.target.value }))
                              }
                            >
                              <option value="">Uncategorized</option>
                              {data.categories.map((category) => (
                                <option key={category.id} value={String(category.id)}>
                                  {category.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            <span>Notes for {item.name}</span>
                            <input
                              aria-label={`Notes for ${item.name}`}
                              value={editForm.notes}
                              onChange={(event) =>
                                setEditForm((current) => ({ ...current, notes: event.target.value }))
                              }
                            />
                          </label>
                        </div>
                      ) : (
                        <span className={item.is_purchased ? "item-name purchased" : "item-name"}>
                          {item.name}
                        </span>
                      )}
                      {item.new_during_trip ? <span className="new-badge">New</span> : null}
                    </div>
                    <div className="item-meta">
                      {editingItemId === item.id ? null : item.quantity ? <span>{item.quantity}</span> : null}
                      {editingItemId === item.id ? null : item.notes ? <span>{item.notes}</span> : null}
                      {editingItemId === item.id ? (
                        <button
                          className="primary-button"
                          onClick={() => handleSaveItem(item)}
                          type="button"
                        >
                          Save {editForm.name || item.name}
                        </button>
                      ) : (
                        <button className="ghost-button" onClick={() => startEditingItem(item)} type="button">
                          Edit {item.name}
                        </button>
                      )}
                      <button className="ghost-button" onClick={() => handleDeleteItem(item)} type="button">
                        Delete {item.name}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
