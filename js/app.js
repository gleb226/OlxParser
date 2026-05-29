const form = document.querySelector("#searchForm");
const results = document.querySelector("#results");
const template = document.querySelector("#resultTemplate");
const recentTemplate = document.querySelector("#recentTemplate");
const recentSearches = document.querySelector("#recentSearches");
const clearRecent = document.querySelector("#clearRecent");
const statusText = document.querySelector("#statusText");
const statusDot = document.querySelector("#statusDot");
const resultCount = document.querySelector("#resultCount");
const queryInput = document.querySelector("#query");
const minPriceInput = document.querySelector("#minPrice");
const maxPriceInput = document.querySelector("#maxPrice");
const priceCurrencyInput = document.querySelector("#priceCurrency");
const categoryInput = document.querySelector("#category");
const cityInput = document.querySelector("#city");
const sellerTypeInput = document.querySelector("#sellerType");
const sortOrderInput = document.querySelector("#sortOrder");

const API_PORTS = ["8000", "5000", "8212", "8080", "3000", "3001", "3002"];
const RECENT_KEY = "olxRecentSearches";
let apiBaseCache = null;

const setStatus = (message, loading = false) => {
  statusText.textContent = message;
  statusDot.classList.toggle("app__status-dot--loading", loading);
};

const normalizePrice = (value) => {
  const trimmed = value.trim();
  return trimmed === "" || trimmed === "-" ? "" : trimmed.replace(/\s+/g, "");
};

const pluralResults = (count) => {
  if (count % 10 === 1 && count % 100 !== 11) return `${count} результат`;
  if ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) return `${count} результати`;
  return `${count} результатів`;
};

const labels = {
  seller: {
    all: "Усі автори",
    private: "Приватні",
    business: "Бізнес",
    unknown: "Автор",
  },
  category: {
    all: "усі розділи",
    cars: "авто",
    phones: "смартфони",
    laptops: "ноутбуки",
    tablets: "планшети",
    audio: "аудіо",
    appliances: "техніка",
    real_estate: "нерухомість",
    house_garden: "дім і сад",
    furniture: "меблі",
    fashion: "стиль",
    kids: "дитяче",
    sports: "спорт",
    jobs: "робота",
  },
  city: {
    all: "Вся Україна",
    kyiv: "Київ",
    kharkiv: "Харків",
    odesa: "Одеса",
    dnipro: "Дніпро",
    lviv: "Львів",
    zaporizhzhia: "Запоріжжя",
    vinnytsia: "Вінниця",
    cherkasy: "Черкаси",
    chernihiv: "Чернігів",
    chernivtsi: "Чернівці",
    ivano_frankivsk: "Івано-Франківськ",
    kropyvnytskyi: "Кропивницький",
    lutsk: "Луцьк",
    mykolaiv: "Миколаїв",
    poltava: "Полтава",
    rivne: "Рівне",
    sumy: "Суми",
    ternopil: "Тернопіль",
    uzhhorod: "Ужгород",
    khmelnytskyi: "Хмельницький",
    zhytomyr: "Житомир",
  },
  sort: {
    asc: "спочатку дешевші",
    desc: "спочатку дорожчі",
  },
};

const enhanceSelect = (select) => {
  const isCity = select.id === "city";
  const control = document.createElement("div");
  control.className = `select-control ${isCity ? "select-control--searchable" : ""}`;

  const button = document.createElement("button");
  button.className = "select-control__button";
  button.type = "button";
  button.setAttribute("aria-haspopup", "listbox");
  button.setAttribute("aria-expanded", "false");

  const value = document.createElement("span");
  value.className = "select-control__value";

  const chevron = document.createElement("span");
  chevron.className = "select-control__chevron";
  chevron.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M6 9l6 6 6-6"/></svg>';

  const menu = document.createElement("div");
  menu.className = "select-control__menu";
  menu.setAttribute("role", "listbox");

  if (isCity) {
    const searchWrapper = document.createElement("div");
    searchWrapper.className = "select-control__search";
    const searchInput = document.createElement("input");
    searchInput.className = "select-control__input";
    searchInput.placeholder = "Пошук міста або введіть своє...";
    searchInput.autocomplete = "off";
    searchWrapper.appendChild(searchInput);
    menu.appendChild(searchWrapper);

    searchInput.addEventListener("input", () => {
      const term = searchInput.value.toLowerCase().trim();
      let found = false;
      [...menu.querySelectorAll(".select-control__option")].forEach(opt => {
        if (opt.classList.contains("select-control__option--custom")) return;
        const matches = term.length >= 2 ? opt.textContent.toLowerCase().includes(term) : true;
        opt.hidden = !matches;
        if (matches && term.length >= 2) found = true;
      });

      let customOpt = menu.querySelector(".select-control__option--custom");
      if (term.length >= 2 && !found) {
        if (!customOpt) {
          customOpt = document.createElement("button");
          customOpt.className = "select-control__option select-control__option--custom";
          customOpt.type = "button";
          customOpt.setAttribute("role", "option");
          menu.appendChild(customOpt);
        }
        customOpt.textContent = `Шукати в місті: ${searchInput.value}`;
        customOpt.dataset.value = "custom:" + searchInput.value;
        customOpt.hidden = false;
        
        customOpt.onclick = () => {
          select.dataset.customCity = searchInput.value;
          select.value = "all";
          value.textContent = searchInput.value;
          control.classList.remove("select-control--open");
          button.setAttribute("aria-expanded", "false");
          select.dispatchEvent(new Event("change", { bubbles: true }));
        };
      } else if (customOpt) {
        customOpt.hidden = true;
      }
    });
  }

  const sync = () => {
    const customValue = select.dataset.customCity;
    if (customValue && select.value === "all") {
      value.textContent = customValue;
    } else {
      const selected = select.options[select.selectedIndex];
      value.textContent = selected ? selected.textContent : "";
    }
    
    [...menu.querySelectorAll(".select-control__option")].forEach((item) => {
      const isSelected = item.dataset.value === select.value && !select.dataset.customCity;
      item.classList.toggle("select-control__option--selected", isSelected);
      item.setAttribute("aria-selected", isSelected ? "true" : "false");
    });
  };

  [...select.options].forEach((option) => {
    const item = document.createElement("button");
    item.className = "select-control__option";
    item.type = "button";
    item.dataset.value = option.value;
    item.textContent = option.textContent;
    item.setAttribute("role", "option");
    item.addEventListener("click", () => {
      delete select.dataset.customCity;
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      control.classList.remove("select-control--open");
      button.setAttribute("aria-expanded", "false");
      sync();
    });
    menu.appendChild(item);
  });

  button.append(value, chevron);
  control.append(button, menu);
  select.after(control);
  select.classList.add("search-form__select--native");

  button.addEventListener("click", () => {
    const wasOpen = control.classList.contains("select-control--open");
    document.querySelectorAll(".select-control--open").forEach((item) => {
      item.classList.remove("select-control--open");
      item.querySelector(".select-control__button")?.setAttribute("aria-expanded", "false");
    });
    if (!wasOpen) {
      control.classList.add("select-control--open");
      button.setAttribute("aria-expanded", "true");
      if (isCity) {
        const searchInput = menu.querySelector(".select-control__input");
        searchInput.value = "";
        searchInput.dispatchEvent(new Event("input"));
        setTimeout(() => searchInput.focus(), 10);
      }
    }
  });

  select.addEventListener("change", sync);
  sync();
};

document.addEventListener("click", (event) => {
  if (!event.target.closest(".select-control")) {
    document.querySelectorAll(".select-control--open").forEach((item) => {
      item.classList.remove("select-control--open");
      item.querySelector(".select-control__button")?.setAttribute("aria-expanded", "false");
    });
  }
});

[priceCurrencyInput, categoryInput, cityInput, sellerTypeInput, sortOrderInput].forEach(enhanceSelect);

const apiCandidates = () => {
  const candidates = [];
  if (window.location.protocol !== "file:") candidates.push(window.location.origin);
  API_PORTS.forEach((port) => {
    candidates.push(`http://127.0.0.1:${port}`);
    candidates.push(`http://localhost:${port}`);
  });
  return [...new Set(candidates)];
};

const findApiBase = async () => {
  if (apiBaseCache) return apiBaseCache;
  for (const base of apiCandidates()) {
    try {
      const response = await fetch(`${base}/api/health`, { cache: "no-store" });
      const payload = await response.json();
      if (payload.ok === true && payload.service === "olx-parser") {
        apiBaseCache = base;
        return apiBaseCache;
      }
    } catch {}
  }
  throw new Error("Локальний сервер не знайдено");
};

const fetchSearch = async (params) => {
  const base = await findApiBase();
  const response = await fetch(`${base}/api/search?${params.toString()}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Помилка пошуку");
  return payload;
};

const imageSource = (url) => {
  if (!url || !apiBaseCache) return "";
  return `${apiBaseCache}/api/image?url=${encodeURIComponent(url)}`;
};

const readRecent = () => {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
};

const writeRecent = (items) => localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, 6)));

const currentSearch = () => ({
  query: queryInput.value.trim(),
  minPrice: normalizePrice(minPriceInput.value),
  maxPrice: normalizePrice(maxPriceInput.value),
  priceCurrency: priceCurrencyInput.value,
  category: categoryInput.value,
  city: cityInput.value,
  cityQuery: cityInput.dataset.customCity || "",
  sellerType: sellerTypeInput.value,
  sort: sortOrderInput.value,
});

const saveRecent = (search) => {
  if (!search.query) return;
  const items = readRecent().filter((item) => JSON.stringify(item) !== JSON.stringify(search));
  items.unshift(search);
  writeRecent(items);
  renderRecent();
};

const applySearch = (search) => {
  queryInput.value = search.query || "";
  minPriceInput.value = search.minPrice || "";
  maxPriceInput.value = search.maxPrice || "";
  priceCurrencyInput.value = search.priceCurrency || "UAH";
  categoryInput.value = search.category || "all";
  cityInput.value = search.city || "all";
  if (search.cityQuery) cityInput.dataset.customCity = search.cityQuery;
  else delete cityInput.dataset.customCity;
  sellerTypeInput.value = search.sellerType || "all";
  sortOrderInput.value = search.sort || "asc";
  [priceCurrencyInput, categoryInput, cityInput, sellerTypeInput, sortOrderInput].forEach(i => i.dispatchEvent(new Event("change")));
};

const recentMeta = (search) => {
  const price = [
    search.minPrice ? `від ${search.minPrice}` : "",
    search.maxPrice ? `до ${search.maxPrice}` : "",
  ].filter(Boolean).join(" ");
  const cityText = search.cityQuery || labels.city[search.city] || labels.city.all;
  return [
    labels.category[search.category] || labels.category.all,
    cityText,
    labels.seller[search.sellerType] || labels.seller.all,
    price ? `${price} ${search.priceCurrency}` : "",
  ].filter(Boolean).join(" • ");
};

const renderRecent = () => {
  const items = readRecent();
  recentSearches.innerHTML = "";
  clearRecent.disabled = !items.length;
  items.forEach((item) => {
    const node = recentTemplate.content.cloneNode(true);
    node.querySelector(".quick-search__query").textContent = item.query;
    node.querySelector(".quick-search__meta").textContent = recentMeta(item);
    node.querySelector(".quick-search").onclick = () => {
      applySearch(item);
      form.requestSubmit();
    };
    recentSearches.appendChild(node);
  });
};

const detailModal = document.querySelector("#detailModal");
const closeModalBtn = document.querySelector("#closeModal");
const modalBody = document.querySelector("#modalBody");

const currencySymbols = {
  UAH: "₴",
  USD: "$",
  EUR: "€"
};

const openModal = async (item) => {
  detailModal.classList.add("modal--open");
  detailModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  
  modalBody.innerHTML = `
    <div class="detail">
      <div class="detail__gallery">
        <div class="detail__main-img skeleton"></div>
        <div class="detail__thumbs"></div>
      </div>
      <div class="detail__info">
        <div class="skeleton" style="height: 32px; width: 80%"></div>
        <div class="skeleton" style="height: 48px; width: 40%"></div>
        <div class="skeleton" style="height: 100px; width: 100%"></div>
      </div>
    </div>
  `;

  try {
    const base = await findApiBase();
    const response = await fetch(`${base}/api/details?url=${encodeURIComponent(item.url)}`);
    const data = await response.json();
    
    if (!response.ok) throw new Error(data.detail || "Помилка завантаження деталей");

    const images = data.images && data.images.length ? data.images : [item.image];
    
    modalBody.innerHTML = `
      <div class="detail">
        <div class="detail__gallery">
          <img class="detail__main-img" src="${imageSource(images[0])}" alt="${data.title}">
          <div class="detail__thumbs">
            ${images.map((img, i) => `
              <img class="detail__thumb ${i === 0 ? 'detail__thumb--active' : ''}" 
                   src="${imageSource(img)}" 
                   onclick="document.querySelector('.detail__main-img').src=this.src; 
                            document.querySelectorAll('.detail__thumb').forEach(t=>t.classList.remove('detail__thumb--active'));
                            this.classList.add('detail__thumb--active')">
            `).join('')}
          </div>
        </div>
        <div class="detail__info">
          <div class="detail__pricebox">
            <h2 class="detail__title">${data.title}</h2>
            <div class="detail__price">${item.display_price_text}</div>
            ${item.original_price_text !== item.display_price_text ? `<div class="detail__original-price">${item.original_price_text}</div>` : ''}
          </div>
          
          <div class="detail__section">
            <h3 class="detail__section-title">Характеристики</h3>
            <div class="detail__params">
              ${data.parameters && data.parameters.length ? data.parameters.map(p => `
                <div class="detail__param">
                  <span class="detail__param-label">${p.label}</span>
                  <span class="detail__param-value">${p.value}</span>
                </div>
              `).join('') : '<p class="detail__desc">Характеристики не вказані</p>'}
            </div>
          </div>

          <div class="detail__section">
            <h3 class="detail__section-title">Опис</h3>
            <div class="detail__desc">${data.description}</div>
          </div>

          <div class="detail__actions">
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn btn--primary">
              Перейти на OLX
            </a>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    modalBody.innerHTML = `<div class="detail"><p class="detail__desc">Помилка: ${err.message}</p></div>`;
  }
};

const closeModal = () => {
  detailModal.classList.remove("modal--open");
  detailModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
};

closeModalBtn.onclick = closeModal;
detailModal.onclick = (e) => { if (e.target === detailModal) closeModal(); };

const renderResults = (items) => {
  results.innerHTML = "";
  if (!items.length) {
    results.innerHTML = `
      <article class="empty-state">
        <div class="empty-state__icon"></div>
        <h2 class="empty-state__title">Нічого не знайдено</h2>
        <p class="empty-state__text">Спробуйте змінити запит або розширити фільтри цін та локації.</p>
      </article>
    `;
    return;
  }

  items.forEach((item) => {
    const node = template.content.cloneNode(true);
    const card = node.querySelector(".result-card");
    
    // Instead of direct links, we open our detail view
    const openBtn = (e) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      openModal(item);
      return false;
    };

    // Remove href attributes to prevent browser-native navigation and replace with javascript:void(0)
    const mediaLink = node.querySelector(".result-card__media");
    const titleLink = node.querySelector(".result-card__title");
    const actionLink = node.querySelector(".result-card__link");

    [mediaLink, titleLink, actionLink].forEach(el => {
      el.href = "javascript:void(0)";
      el.onclick = openBtn;
      // Add a secondary event listener just in case
      el.addEventListener("click", openBtn);
    });
    
    titleLink.textContent = item.title;
    node.querySelector(".result-card__meta").textContent = [item.location, item.date].filter(Boolean).join(" • ");
    
    const seller = node.querySelector(".result-card__seller");
    seller.textContent = labels.seller[item.seller_type] || "Автор";
    seller.dataset.type = item.seller_type;
    
    node.querySelector(".result-card__currency").textContent = currencySymbols[item.currency] || item.currency;
    node.querySelector(".result-card__price").textContent = item.display_price_text;

    const details = [];
    if (item.original_price_text && item.original_price_text !== item.display_price_text) details.push(item.original_price_text);
    if (item.exchange_rate_text) details.push(item.exchange_rate_text);
    node.querySelector(".result-card__converted").textContent = details.join(" • ");

    const img = node.querySelector(".result-card__image");
    const placeholder = node.querySelector(".result-card__placeholder");
    if (item.image) {
      img.src = imageSource(item.image);
      img.style.opacity = "0";
      img.onload = () => {
        placeholder.style.display = "none";
        img.style.opacity = "1";
      };
      img.onerror = () => {
        img.remove();
        placeholder.style.display = "flex";
      };
    } else {
      img.remove();
      placeholder.style.display = "flex";
    }
    results.appendChild(node);
  });
};

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const search = currentSearch();
  const params = new URLSearchParams({
    query: search.query,
    min_price: search.minPrice,
    max_price: search.maxPrice,
    price_currency: search.priceCurrency,
    category: search.category,
    city: search.city,
    city_query: search.cityQuery,
    seller_type: search.sellerType,
    sort: search.sort,
  });

  setStatus("Шукаю найкращі пропозиції...", true);
  resultCount.textContent = "завантаження...";
  
  try {
    const payload = await fetchSearch(params);
    saveRecent(search);
    renderResults(payload.items);
    resultCount.textContent = pluralResults(payload.items.length);
    setStatus("Пошук завершено");
  } catch (err) {
    setStatus("Сталася помилка");
    resultCount.textContent = "0 знайдено";
  }
});

clearRecent.onclick = () => {
  writeRecent([]);
  renderRecent();
};

renderRecent();
