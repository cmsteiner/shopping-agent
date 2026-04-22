import { useEffect, useRef, useState } from "react";

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

function findCategoryName(categories, categoryId) {
  if (categoryId === "" || categoryId == null) {
    return "Uncategorized";
  }
  const category = categories.find((entry) => String(entry.id) === String(categoryId));
  return category?.name || "Uncategorized";
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

function updateCategoryInData(data, updatedCategory) {
  return {
    ...data,
    categories: data.categories.map((category) =>
      category.id === updatedCategory.id ? { ...category, ...updatedCategory } : category
    ),
    items_by_category: data.items_by_category.map((group) => {
      if (group.category.id !== updatedCategory.id) {
        return group;
      }
      return {
        ...group,
        category: { ...group.category, ...updatedCategory },
        items: group.items.map((item) => ({
          ...item,
          category_name: updatedCategory.name
        }))
      };
    })
  };
}

function addCategoryToData(data, category) {
  if (data.categories.some((entry) => entry.id === category.id)) {
    return updateCategoryInData(data, category);
  }
  return {
    ...data,
    categories: [...data.categories, category]
  };
}

function removeCategoryFromData(data, categoryId) {
  return {
    ...data,
    categories: data.categories.filter((category) => category.id !== categoryId),
    items_by_category: data.items_by_category.filter((group) => group.category.id !== categoryId)
  };
}

export default function App({ token }) {
  const [state, setState] = useState(initialState);
  const [form, setForm] = useState({
    name: "",
    quantity: "",
    category_id: "",
    notes: ""
  });
  const [categoryName, setCategoryName] = useState("");
  const [categoryDeleteTarget, setCategoryDeleteTarget] = useState(null);
  const [categoryMessage, setCategoryMessage] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [categoryEditName, setCategoryEditName] = useState("");
  const [editingItemId, setEditingItemId] = useState(null);
  const [editForm, setEditForm] = useState({
    name: "",
    quantity: "",
    category_id: "",
    notes: ""
  });
  const [tripReview, setTripReview] = useState(null);
  const [duplicatePrompt, setDuplicatePrompt] = useState(null);
  const [conflictPrompt, setConflictPrompt] = useState(null);
  const lastEventIdRef = useRef(0);

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

  useEffect(() => {
    if (state.status !== "ready") {
      return undefined;
    }
    if (typeof EventSource === "undefined") {
      return undefined;
    }

    const eventSource = new EventSource(`/api/events/stream?token=${token}&last_event_id=${lastEventIdRef.current}`);
    const handleItemUpdated = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
        }
      }));
    };
    const handleItemCreated = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
        }
      }));
    };
    const handleItemDeleted = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: removeItemFromGroups(current.data.items_by_category, payload.id)
        }
      }));
    };
    const handleCategoryCreated = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: addCategoryToData(current.data, payload.category)
      }));
    };
    const handleCategoryUpdated = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: updateCategoryInData(current.data, payload.category)
      }));
    };
    const handleCategoryDeleted = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: removeCategoryFromData(current.data, payload.category.id)
      }));
    };
    const handleTripStarted = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          trip: payload.trip
        }
      }));
    };
    const handleTripCompleted = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          trip: null
        }
      }));
    };
    const handleListReplaced = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          list: payload.new_active_list,
          items_by_category: buildGroupsFromItems(current.data.categories, payload.carried_over_items)
        }
      }));
    };
    const handleDuplicateResolved = (event) => {
      lastEventIdRef.current = Number(event.lastEventId || lastEventIdRef.current);
      const payload = JSON.parse(event.data);
      setState((current) => {
        if (payload.resolved_item) {
          return {
            ...current,
            data: {
              ...current.data,
              items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.resolved_item)
            }
          };
        }
        if (payload.removed_pending_item_id) {
          return {
            ...current,
            data: {
              ...current.data,
              items_by_category: removeItemFromGroups(current.data.items_by_category, payload.removed_pending_item_id)
            }
          };
        }
        return current;
      });
    };

    eventSource.addEventListener("item.updated", handleItemUpdated);
    eventSource.addEventListener("item.created", handleItemCreated);
    eventSource.addEventListener("item.deleted", handleItemDeleted);
    eventSource.addEventListener("category.created", handleCategoryCreated);
    eventSource.addEventListener("category.updated", handleCategoryUpdated);
    eventSource.addEventListener("category.deleted", handleCategoryDeleted);
    eventSource.addEventListener("trip.started", handleTripStarted);
    eventSource.addEventListener("trip.completed", handleTripCompleted);
    eventSource.addEventListener("list.replaced", handleListReplaced);
    eventSource.addEventListener("item.duplicate_resolved", handleDuplicateResolved);

    return () => {
      eventSource.close();
    };
  }, [state.status, token]);

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

  function categoryItemCount(categoryId) {
    const group = data.items_by_category.find((entry) => (entry.category.id ?? null) === (categoryId ?? null));
    return group ? group.items.length : 0;
  }

  async function handleCreateCategory(event) {
    event.preventDefault();
    setCategoryMessage("");
    const response = await fetch("/api/categories", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({ name: categoryName })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        categories: [...current.data.categories, payload.category]
      }
    }));
    setCategoryName("");
  }

  async function handleDeleteCategory(category) {
    setCategoryMessage("");
    const response = await fetch(`/api/categories/${category.id}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: category.version,
        confirm: true
      })
    });
    if (!response.ok) {
      const payload = await response.json();
      setCategoryMessage(payload.error?.message || "Unable to delete category.");
      return;
    }
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        categories: current.data.categories.filter((entry) => entry.id !== category.id)
      }
    }));
    setCategoryDeleteTarget(null);
  }

  function startEditingCategory(category) {
    setEditingCategoryId(category.id);
    setCategoryEditName(category.name);
    setCategoryMessage("");
  }

  async function handleRenameCategory(category) {
    const response = await fetch(`/api/categories/${category.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: category.version,
        name: categoryEditName
      })
    });
    if (response.status === 409) {
      const payload = await response.json();
      setConflictPrompt(payload.conflict);
      return;
    }
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => ({
      ...current,
      data: updateCategoryInData(current.data, payload.category)
    }));
    setEditingCategoryId(null);
    setCategoryEditName("");
  }

  async function handleAddItem(event) {
    event.preventDefault();
    const optimisticId = `temp-${Date.now()}`;
    const optimisticItem = {
      id: optimisticId,
      name: form.name,
      quantity: form.quantity || "1",
      unit: null,
      notes: form.notes || "",
      category_id: form.category_id === "" ? null : Number(form.category_id),
      category_name: findCategoryName(data.categories, form.category_id),
      status: "ACTIVE",
      is_purchased: false,
      new_during_trip: Boolean(data.trip),
      version: 0,
      created_at: null,
      updated_at: null
    };
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: upsertItemIntoGroups(current.data.items_by_category, optimisticItem)
      }
    }));
    setForm({ name: "", quantity: "", category_id: "", notes: "" });

    const response = await fetch("/api/items", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify(form)
    });
    if (!response.ok) {
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: removeItemFromGroups(current.data.items_by_category, optimisticId)
        }
      }));
      return;
    }
    const payload = await response.json();
    if (payload.pending_duplicate) {
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: removeItemFromGroups(current.data.items_by_category, optimisticId)
        }
      }));
      setDuplicatePrompt(payload.pending_duplicate);
      return;
    }
    setState((current) => ({
      ...current,
      data: {
        ...current.data,
        items_by_category: upsertItemIntoGroups(
          removeItemFromGroups(current.data.items_by_category, optimisticId),
          payload.item
        )
      }
    }));
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
    const clientPayload = {
      name: editForm.name,
      quantity: editForm.quantity,
      notes: editForm.notes,
      category_id: editForm.category_id === "" ? null : Number(editForm.category_id)
    };
    const categoryId = editForm.category_id === "" ? null : Number(editForm.category_id);
    const response = await fetch(`/api/items/${item.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        base_version: item.version,
        ...clientPayload
      })
    });
    if (response.status === 409) {
      const payload = await response.json();
      setConflictPrompt(payload.conflict);
      return;
    }
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

  async function handleDuplicateDecision(decision) {
    if (!duplicatePrompt) {
      return;
    }
    const response = await fetch(`/api/duplicates/${duplicatePrompt.pending_confirmation_id}/resolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({ decision })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (payload.resolved_item) {
      setState((current) => ({
        ...current,
        data: {
          ...current.data,
          items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.resolved_item)
        }
      }));
    }
    setDuplicatePrompt(null);
  }

  async function handleConflictDecision(decision) {
    if (!conflictPrompt) {
      return;
    }
    if (decision === "keep_server") {
      setState((current) => {
        if (conflictPrompt.entity_type === "category") {
          return {
            ...current,
            data: updateCategoryInData(current.data, conflictPrompt.server_payload)
          };
        }
        return {
          ...current,
          data: {
            ...current.data,
            items_by_category: upsertItemIntoGroups(current.data.items_by_category, conflictPrompt.server_payload)
          }
        };
      });
      setConflictPrompt(null);
      setEditingItemId(null);
      setEditingCategoryId(null);
      return;
    }

    const response = await fetch("/api/conflicts/resolve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-App-Token": token
      },
      body: JSON.stringify({
        entity_type: conflictPrompt.entity_type,
        entity_id: conflictPrompt.entity_id,
        decision,
        server_version: conflictPrompt.server_version,
        client_payload: conflictPrompt.client_payload
      })
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    setState((current) => {
      if (payload.entity_type === "category") {
        return {
          ...current,
          data: updateCategoryInData(current.data, payload.category)
        };
      }
      return {
        ...current,
        data: {
          ...current.data,
          items_by_category: upsertItemIntoGroups(current.data.items_by_category, payload.item)
        }
      };
    });
    setConflictPrompt(null);
    setEditingItemId(null);
    setEditingCategoryId(null);
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

      {duplicatePrompt ? (
        <section className="overlay-panel">
          <h2>Possible duplicate item</h2>
          <p>
            Existing: {duplicatePrompt.existing_item.name}
            {duplicatePrompt.existing_item.notes ? ` (${duplicatePrompt.existing_item.notes})` : ""}
          </p>
          <p>
            New: {duplicatePrompt.pending_item.name}
            {duplicatePrompt.pending_item.notes ? ` (${duplicatePrompt.pending_item.notes})` : ""}
          </p>
          <div className="overlay-actions">
            {duplicatePrompt.options.includes("merge") ? (
              <button className="primary-button" onClick={() => handleDuplicateDecision("merge")} type="button">
                Merge items
              </button>
            ) : null}
            {duplicatePrompt.options.includes("keep_separate") ? (
              <button className="ghost-button" onClick={() => handleDuplicateDecision("keep_separate")} type="button">
                Keep separate
              </button>
            ) : null}
            {duplicatePrompt.options.includes("cancel") ? (
              <button className="ghost-button" onClick={() => handleDuplicateDecision("cancel")} type="button">
                Cancel add
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {conflictPrompt ? (
        <section className="overlay-panel">
          <h2>{conflictPrompt.entity_type === "category" ? "Resolve category conflict" : "Resolve edit conflict"}</h2>
          <p>Server version: {conflictPrompt.server_payload.name}</p>
          <p>My version: {conflictPrompt.client_payload.name}</p>
          <div className="overlay-actions">
            <button
              className="primary-button"
              onClick={() => handleConflictDecision("overwrite_with_client")}
              type="button"
            >
              {conflictPrompt.entity_type === "category" ? "Keep my category name" : "Keep my changes"}
            </button>
            <button className="ghost-button" onClick={() => handleConflictDecision("keep_server")} type="button">
              {conflictPrompt.entity_type === "category" ? "Keep server category" : "Keep server version"}
            </button>
          </div>
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
            <span>Category</span>
            <select
              aria-label="Category"
              name="category_id"
              value={form.category_id}
              onChange={(event) => setForm((current) => ({ ...current, category_id: event.target.value }))}
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

      <section className="category-manager">
        <div className="category-manager-header">
          <h2>Categories</h2>
        </div>
        <form className="category-form" onSubmit={handleCreateCategory}>
          <label>
            <span>New category name</span>
            <input
              aria-label="New category name"
              name="new-category-name"
              value={categoryName}
              onChange={(event) => setCategoryName(event.target.value)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={!categoryName.trim()}>
            Add category
          </button>
        </form>
        {categoryMessage ? <p className="category-message">{categoryMessage}</p> : null}
        {categoryDeleteTarget ? (
          <div className="overlay-actions category-confirmation">
            <span>Delete category {categoryDeleteTarget.name}?</span>
            <button
              className="primary-button"
              onClick={() => handleDeleteCategory(categoryDeleteTarget)}
              type="button"
            >
              Confirm delete {categoryDeleteTarget.name}
            </button>
            <button className="ghost-button" onClick={() => setCategoryDeleteTarget(null)} type="button">
              Cancel
            </button>
          </div>
        ) : null}
        <ul className="category-chip-list">
          {data.categories.map((category) => (
            <li className="category-chip" key={category.id}>
              {editingCategoryId === category.id ? (
                <>
                  <label className="category-inline-editor">
                    <span>Rename category {category.name}</span>
                    <input
                      aria-label={`Rename category ${category.name}`}
                      value={categoryEditName}
                      onChange={(event) => setCategoryEditName(event.target.value)}
                    />
                  </label>
                  <button className="primary-button" onClick={() => handleRenameCategory(category)} type="button">
                    Save category {categoryEditName || category.name}
                  </button>
                </>
              ) : (
                <>
                  <span>{category.name}</span>
                  <button className="ghost-button" onClick={() => startEditingCategory(category)} type="button">
                    Rename category {category.name}
                  </button>
                </>
              )}
              <button
                className="ghost-button"
                onClick={() => setCategoryDeleteTarget(category)}
                type="button"
                disabled={categoryItemCount(category.id) > 0}
              >
                Delete category {category.name}
              </button>
              {categoryItemCount(category.id) > 0 ? (
                <span className="category-hint">Move all items out of this category before deleting it.</span>
              ) : null}
            </li>
          ))}
        </ul>
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
