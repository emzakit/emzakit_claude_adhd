// The roadmap board. roadmap.html embeds the cards, the categories and flags, and every label; this draws them.
// Opened as a plain file the board is read-only. Served by tools/roadmap_board.py
// (the open-roadmap launcher in tools/) it can save, so cards can be dragged, edited and added, and their files opened.
(() => {
  const data = JSON.parse(document.getElementById("board-data").textContent);
  const labels = data.text; // every word this script shows; they live in build_record.py
  const board = document.getElementById("board");
  const status = document.getElementById("board-status");
  const dialog = document.getElementById("card-dialog");
  const form = dialog.querySelector("form");
  const flagBoxes = document.getElementById("card-flags");
  const manage = document.getElementById("manage-dialog");
  const manageOpen = document.getElementById("manage-open");
  const manageLists = [...manage.querySelectorAll("fieldset")]; // data-list: "categories" and "flags"
  const rowTemplate = document.getElementById("manage-row");
  const token = location.hash.slice(1);
  // WEB and unquote() are intentionally separate from link_path() in roadmap_board.py: this page only decides how
  // a link is drawn; the helper decides again, on its own, what is opened.
  const WEB = /^https?:\/\//i; // only a link that passes this test is ever put in an href
  const COLOUR = /^#[0-9a-f]{6}$/i;
  let cards = data.cards;
  let settings = data.board; // { categories, flags }, each a list of { name, colour }
  let version = null; // what the files looked like when we read them; null means read-only
  let dragged = null;
  let editing = null;

  const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local time
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  // A colour reaches the page as one custom property set through the CSSOM, never as style text.
  const tinted = (node, colour) => {
    if (COLOUR.test(colour)) node.style.setProperty("--chip", colour);
    return node;
  };
  const colourOf = (list, name) => (settings[list].find((item) => item.name === name) || {}).colour;
  // Windows "Copy as path" wraps a path in double quotes.
  const unquote = (link) => {
    const bare = link.trim();
    return bare.length > 1 && bare.startsWith('"') && bare.endsWith('"') ? bare.slice(1, -1).trim() : bare;
  };
  // Set a field, or remove it when there is nothing to store: the record has no empty strings or lists.
  const put = (card, key, value) => {
    if (value && value.length) card[key] = value;
    else delete card[key];
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
        const add = element("button", "", labels.add_card);
        add.type = "button";
        add.addEventListener("click", () => openDialog(null, key));
        column.append(add);
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
    const tags = element("div", "tags");
    if (card.category) {
      const colour = colourOf("categories", card.category);
      tinted(node, colour); // the card's left border
      tags.append(tinted(element("span", "chip", card.category), colour));
    }
    for (const name of card.flags || []) tags.append(tinted(element("span", "flag", name), colourOf("flags", name)));
    node.append(element("div", "stamp", card.id + " · " + card.date));
    if (tags.childElementCount) node.append(tags);
    node.append(element("h3", "", card.title));
    if (card.note) node.append(element("p", "", card.note));
    if (card.links) node.append(linksNode(card));
    if (card.research) {
      const report = element("a", "", labels.report);
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
      const edit = element("button", "", labels.edit);
      edit.type = "button";
      edit.addEventListener("click", () => openDialog(card, card.status));
      node.append(edit);
    }
    return node;
  }

  function linksNode(card) {
    const list = element("ul", "links");
    card.links.forEach((link, index) => {
      const item = element("li");
      item.append(linkNode(card.id, unquote(link), index));
      list.append(item);
    });
    return list;
  }

  // A web address is a link the browser opens. A path is a button: the helper opens the file, by card id
  // and position, so the page never sends a path.
  function linkNode(id, link, index) {
    if (WEB.test(link)) {
      const anchor = element("a", "", link);
      anchor.href = link;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      return anchor;
    }
    if (!version) return element("span", "", link);
    const button = element("button", "", link.split(/[\\/]/).filter(Boolean).pop() || link);
    button.type = "button";
    button.title = link;
    button.addEventListener("click", () => openLink(id, index));
    return button;
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
    const shown = card || { status: columnKey };
    const fields = form.elements;
    fields.category.length = 1; // keep "None", refill the rest: the categories may have changed
    for (const { name } of settings.categories) fields.category.add(new Option(name, name));
    flagBoxes.querySelectorAll("label").forEach((label) => label.remove());
    for (const { name } of settings.flags) {
      const box = element("input");
      box.type = "checkbox";
      box.value = name;
      box.checked = (shown.flags || []).includes(name);
      const label = element("label");
      label.append(box, name);
      flagBoxes.append(label);
    }
    flagBoxes.hidden = !settings.flags.length;
    fields.title.value = shown.title || "";
    fields.note.value = shown.note || "";
    fields.status.value = shown.status;
    fields.category.value = shown.category || "";
    fields.links.value = (shown.links || []).join("\n");
    dialog.showModal();
  }

  // Save is each form's only submit button, so Enter in a text field saves. Cancel is a plain button.
  for (const cancel of document.querySelectorAll('dialog button[value="cancel"]')) {
    cancel.addEventListener("click", () => cancel.closest("dialog").close());
  }

  // The form's submit event, not the dialog's close event: close waits for the next painted frame.
  form.addEventListener("submit", () => {
    const title = form.elements.title.value.trim();
    if (!title) return;
    let card = editing;
    if (!card) {
      const highest = Math.max(0, ...cards.map((other) => Number(other.id.slice(2))));
      card = { id: "R-" + String(highest + 1).padStart(3, "0"), title, status: "", date: today() };
      cards.push(card);
    }
    card.title = title;
    put(card, "note", form.elements.note.value.trim());
    put(card, "category", form.elements.category.value);
    put(card, "flags", [...flagBoxes.querySelectorAll("input:checked")].map((box) => box.value));
    put(card, "links", form.elements.links.value.split("\n").map(unquote).filter(Boolean));
    if (card.status !== form.elements.status.value) place(card, form.elements.status.value, null);
    render();
    save();
  });

  // One row of the "Categories and flags" dialog: name, colour, Remove. `item` is null for a new one.
  function addRow(list, item) {
    const row = rowTemplate.content.firstElementChild.cloneNode(true);
    const [name, colour, remove] = row.children;
    if (item) {
      name.value = item.name;
      colour.value = item.colour;
      row.dataset.was = item.name; // the name the cards still carry
    }
    remove.addEventListener("click", () => row.remove());
    list.lastElementChild.before(row); // above the "+ Add" button
  }

  for (const list of manageLists) list.lastElementChild.addEventListener("click", () => addRow(list, null));

  manageOpen.addEventListener("click", () => {
    for (const list of manageLists) {
      list.querySelectorAll(".manage-row").forEach((row) => row.remove());
      for (const item of settings[list.dataset.list]) addRow(list, item);
    }
    manage.showModal();
  });

  manage.querySelector("form").addEventListener("submit", () => {
    const renamed = {}; // per list: old name -> new name, for each one that was kept
    for (const list of manageLists) {
      const rows = [...list.querySelectorAll(".manage-row")].map((row) => (
        { was: row.dataset.was, name: row.children[0].value.trim(), colour: row.children[1].value }));
      settings[list.dataset.list] = rows.map(({ name, colour }) => ({ name, colour }));
      const kept = rows.filter((row) => row.was !== undefined); // a new row has no old name
      renamed[list.dataset.list] = new Map(kept.map((row) => [row.was, row.name]));
    }
    for (const card of cards) { // a renamed one follows its new name; a removed one leaves the card
      put(card, "category", renamed.categories.get(card.category));
      put(card, "flags", (card.flags || []).map((name) => renamed.flags.get(name)).filter(Boolean));
    }
    render();
    save(); // cards and settings travel together, so the server checks them against each other
  });

  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Board-Token": token },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    return result;
  }

  async function openLink(id, index) {
    try {
      const result = await post("api/open", { version, id, index });
      status.textContent = "opened" in result ? labels.opened + result.opened : labels.revealed + result.revealed;
    } catch (error) {
      await load(); // the board may be out of date: the helper refuses a link clicked on a stale one
      status.textContent = labels.not_opened + error.message;
    }
  }

  async function save() {
    try {
      ({ version } = await post("api/roadmap", { version, cards, board: settings }));
      status.textContent = labels.saved + " " + labels.open;
    } catch (error) {
      await load(); // the files are the truth: show what is really there
      status.textContent = labels.not_saved + error.message;
    }
  }

  async function load() {
    try {
      const response = await fetch("api/roadmap", { headers: { "X-Board-Token": token } });
      if (!response.ok) throw new Error();
      ({ cards, version, board: settings } = await response.json());
      status.textContent = labels.open;
    } catch {
      version = null;
      status.textContent = labels.locked;
    }
    manageOpen.hidden = !version;
    render();
  }

  load();
})();
