const form = document.querySelector("#searchForm");
const results = document.querySelector("#results");
const template = document.querySelector("#resultTemplate");
const statusText = document.querySelector("#statusText");
const statusDot = document.querySelector("#statusDot");
const resultCount = document.querySelector("#resultCount");

const setStatus = (message, loading = false) => {
  statusText.textContent = message;
  statusDot.classList.toggle("is-loading", loading);
};

const normalizePrice = (value) => {
  const trimmed = value.trim();
  return trimmed === "" || trimmed === "-" ? "" : trimmed.replace(/\s+/g, "");
};

const renderEmpty = (title, message) => {
  results.innerHTML = `
    <article class="empty-state">
      <div class="empty-state__icon"></div>
      <h2>${title}</h2>
      <p>${message}</p>
    </article>
  `;
};

const renderResults = (items) => {
  results.innerHTML = "";

  if (!items.length) {
    renderEmpty("Нічого не знайдено", "Спробуй змінити назву товару або діапазон ціни.");
    return;
  }

  items.forEach((item, index) => {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".result-card");
    const imageLink = node.querySelector(".result-card__image");
    const image = node.querySelector("img");
    const title = node.querySelector(".result-card__title");
    const meta = node.querySelector(".result-card__meta");
    const price = node.querySelector(".result-card__price");
    const link = node.querySelector(".result-card__link");

    card.style.animationDelay = `${Math.min(index * 55, 440)}ms`;
    imageLink.href = item.url;
    title.href = item.url;
    link.href = item.url;
    title.textContent = item.title;
    meta.textContent = [item.location, item.date].filter(Boolean).join(" • ") || "OLX";
    price.textContent = item.price_text || "Ціну не вказано";

    if (item.image) {
      image.src = item.image;
      image.alt = item.title;
    } else {
      image.remove();
    }

    results.appendChild(node);
  });
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const params = new URLSearchParams({
    query: document.querySelector("#query").value.trim(),
    min_price: normalizePrice(document.querySelector("#minPrice").value),
    max_price: normalizePrice(document.querySelector("#maxPrice").value),
    sort: document.querySelector("#sortOrder").value,
  });

  setStatus("Парсинг OLX...", true);
  resultCount.textContent = "очікування";
  results.innerHTML = "";
  renderEmpty("Сканую оголошення", "Завантажую сторінку OLX і очищую результати.");

  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Помилка пошуку");
    }

    renderResults(payload.items);
    resultCount.textContent = `${payload.items.length} результатів`;
    setStatus("Пошук завершено");
  } catch (error) {
    renderEmpty("Не вдалося виконати пошук", error.message);
    resultCount.textContent = "0 результатів";
    setStatus("Помилка");
  }
});
