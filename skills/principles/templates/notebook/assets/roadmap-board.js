// The roadmap board. roadmap.html embeds the cards; this draws them.
// Opened as a plain file the board is read-only. Served by tools/roadmap_board.py
// (open-roadmap.bat) it can save, so cards can be dragged, edited and added.
(() => {
  const data = JSON.parse(document.getElementById("board-data").textContent);
  const board = document.getElementById("board");
  const status = document.getElementById("board-status");
  const dialog = document.getElementById("card-dialog");
  const form = dialog.querySelector("form");
  const token = location.hash.slice(1);
  let cards = data.cards;
  let version = null; // what the file looked like when we read it; null means read-only
  let dragged = null;
  let editing = null;

  const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local time
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  for (const [key, label] of data.columns) form.elements.status.add(new Option(label, key));

  function render() {
    board.replaceChildren();
    for (const [key, label] of data.columns) {
      const column = element("section", "column");
      const mine = cards.filter((card) => card.status === key);
      const heading = element("h2", "", label + " ");
      heading.append(element("span", "", String(mine.length)));
      column.append(heading);
      for (const card of mine) column.append(cardNode(card));
      if (version) {
        const add = element("button", "", "+ Add card");
        add.type = "button";
        add.addEventListener("click", () => openDialog(null, key));
        column.append(add);
      }
      if (version) {
        column.addEventListener("dragover", (event) => {
          event.preventDefault();
          column.classList.add("over");
        });
        column.addEventListener("dragleave", () => column.classList.remove("over"));
        column.addEventListener("drop", (event) => {
          event.preventDefault();
          const below = [...column.querySelectorAll(".card:not(.dragging)")].find((node) => {
            const box = node.getBoundingClientRect();
            return event.clientY < box.top + box.height / 2;
          });
          move(key, below ? below.dataset.id : null);
        });
      }
      board.append(column);
    }
  }

  function cardNode(card) {
    const node = element("article", "card");
    node.dataset.id = card.id;
    node.append(element("div", "stamp", card.id + " · " + card.date), element("h3", "", card.title));
    if (card.note) node.append(element("p", "", card.note));
    if (card.research) {
      const report = element("a", "", data.report);
      report.href = "research/" + encodeURIComponent(card.research) + ".html";
      const line = element("p");
      line.append(report);
      node.append(line);
    }
    if (version) {
      node.draggable = true;
      node.addEventListener("dragstart", () => {
        dragged = card.id;
        node.classList.add("dragging");
      });
      node.addEventListener("dragend", () => node.classList.remove("dragging"));
      const edit = element("button", "", "Edit");
      edit.type = "button";
      edit.addEventListener("click", () => openDialog(card, card.status));
      node.append(edit);
    }
    return node;
  }

  function place(card, columnKey, beforeId) {
    cards = cards.filter((other) => other !== card);
    if (card.status !== columnKey) {
      card.status = columnKey;
      card.date = today();
    }
    const index = beforeId ? cards.findIndex((other) => other.id === beforeId) : cards.length;
    cards.splice(index, 0, card);
  }

  function move(columnKey, beforeId) {
    const card = cards.find((other) => other.id === dragged);
    if (!card || card.id === beforeId) return;
    const wasAbandoned = card.status === "abandoned";
    place(card, columnKey, beforeId);
    render();
    save();
    if (columnKey === "abandoned" && !wasAbandoned && !card.note) openDialog(card, columnKey); // ask why
  }

  function openDialog(card, columnKey) {
    editing = card;
    form.elements.title.value = card ? card.title : "";
    form.elements.note.value = card && card.note ? card.note : "";
    form.elements.status.value = card ? card.status : columnKey;
    dialog.showModal();
  }

  // The form's submit event, not the dialog's close event: close waits for the next painted frame.
  form.addEventListener("submit", (event) => {
    if (event.submitter.value !== "save") return;
    const title = form.elements.title.value.trim();
    if (!title) return;
    let card = editing;
    if (!card) {
      const highest = Math.max(0, ...cards.map((other) => Number(other.id.slice(2))));
      card = { id: "R-" + String(highest + 1).padStart(3, "0"), title, status: "", date: today() };
      cards.push(card);
    }
    card.title = title;
    const note = form.elements.note.value.trim();
    if (note) card.note = note;
    else delete card.note;
    if (card.status !== form.elements.status.value) place(card, form.elements.status.value, null);
    render();
    save();
  });

  async function save() {
    try {
      const response = await fetch("api/roadmap", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Board-Token": token },
        body: JSON.stringify({ version, cards }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      version = result.version;
      status.textContent = "Saved. " + data.open;
    } catch (error) {
      await load(); // the file is the truth: show what is really there
      status.textContent = "Not saved: " + error.message;
    }
  }

  async function load() {
    try {
      const response = await fetch("api/roadmap", { headers: { "X-Board-Token": token } });
      if (!response.ok) throw new Error();
      ({ cards, version } = await response.json());
      status.textContent = data.open;
    } catch {
      version = null;
      status.textContent = data.locked;
    }
    render();
  }

  load();
})();
