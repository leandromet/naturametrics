/* UmaTerra — demonstrações em rolagem (kit compartilhado)
 *
 * Arquivo compartilhado por hash entre Naturametrics (canônico), Camposcope,
 * Yvynation e muda-clima: edite em naturametrics/reportagem/kit.js e rode
 * scripts/sync_shared_files.py.
 *
 * Uma demonstração é uma página com passos (.rp-passo) à esquerda e uma
 * moldura fixa à direita: um mapa Leaflet persistente (#rp-mapa) e um painel
 * com camadas (.rp-camada). Cada passo declara, em atributos, o que acende:
 *
 *   data-passo   chave do tratador em cfg.passos (e da camada, por padrão)
 *   data-camada  id da .rp-camada a mostrar no painel ("" = nenhuma)
 *   data-mapa    grande | meio | pequeno | lado | oculto
 *   data-bloco   blocos da miniatura da página a acender (separados por vírgula)
 *   data-titulo  título da moldura
 *   data-selo    real | estimado | declarado | ausente | exemplo
 *   data-url     o que a barra da janela mostra
 *
 * Os números vêm de uma rota JSON do próprio aplicativo (cfg.dados), a mesma
 * cadeia de serviços que a interface usa. Nenhum número da página é escrito à
 * mão: o que não chegou fica como "—" e o passo diz que faltou.
 *
 * Dentro do Reflex a página é montada pelo React depois deste script, e pode
 * ser desmontada e remontada numa navegação; por isso iniciar() espera a raiz
 * existir e marca a raiz que já iniciou, em vez de rodar no carregamento.
 */
(function () {
  "use strict";
  if (window.Reportagem) return;

  var LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
  var LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var LEAFLET_CSS_SRI = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
  var LEAFLET_JS_SRI = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";

  // ─── formatação: pt-BR por padrão, en-US numa página <… lang="en"> ──────
  // (definida em montar(); o kit atende uma página por vez)
  var LOCALE = "pt-BR";
  function vazio(v) { return v === null || v === undefined || (typeof v === "number" && !isFinite(v)); }
  var fmt = {
    n: function (v, d) {
      if (vazio(v)) return "—";
      d = d === undefined ? 0 : d;
      return Number(v).toLocaleString(LOCALE, { minimumFractionDigits: d, maximumFractionDigits: d });
    },
    // hectares com casas decimais proporcionais ao tamanho
    ha: function (v) {
      if (vazio(v)) return "—";
      var a = Math.abs(v);
      return fmt.n(v, a < 10 ? 2 : a < 1000 ? 1 : 0) + " ha";
    },
    pct: function (v, d) { return vazio(v) ? "—" : fmt.n(v, d === undefined ? 0 : d) + "%"; },
    sinal: function (v, d) {
      if (vazio(v)) return "—";
      var s = fmt.n(Math.abs(v), d === undefined ? 1 : d);
      return (v > 0 ? "+" : v < 0 ? "−" : "") + s;
    },
    data: function (iso) {
      if (!iso) return "—";
      var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
      if (!m) return String(iso);
      return LOCALE === "pt-BR" ? m[3] + "/" + m[2] + "/" + m[1] : m[1] + "-" + m[2] + "-" + m[3];
    },
    // "2026-10-27T23:43:31+00:00" → "27/10/2026, 20:43" no fuso do leitor
    dataHora: function (iso) {
      if (!iso) return "—";
      var d = new Date(iso);
      return isNaN(d) ? String(iso) : d.toLocaleString(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    },
    esc: function (s) {
      return String(s === null || s === undefined ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
  };

  // ─── gráficos SVG (sempre sobre a moldura clara) ────────────────────────
  var W = 760;
  function svg(h, corpo, rotulo) {
    return '<svg class="rp-sv" viewBox="0 0 ' + W + " " + h + '" role="img" aria-label="' + fmt.esc(rotulo || "") + '">' + corpo + "</svg>";
  }
  function passoEixo(max) {
    if (max <= 0) return 1;
    var bruto = max / 4, p = Math.pow(10, Math.floor(Math.log10(bruto))), r = bruto / p;
    return (r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10) * p;
  }
  // casas decimais que um passo de eixo precisa (0,25 → 2; 0,5 → 1; 5 → 0)
  function casas(passo) { for (var d = 0; d < 4; d++) { if (Math.abs(passo * Math.pow(10, d) - Math.round(passo * Math.pow(10, d))) < 1e-6) return d; } return 3; }
  // rótulo de categoria a cada `cada` posições; o último só se não encostar no anterior
  function rotular(i, n, cada) { return i % cada === 0 || (i === n - 1 && (n - 1) % cada > cada / 2); }
  function eixoY(max, x0, x1, y0, y1, unidade, dec) {
    var passo = passoEixo(max), topo = Math.max(passo, Math.ceil(max / passo) * passo), s = "";
    if (dec === undefined) dec = casas(passo);
    for (var v = 0; v <= topo + 1e-9; v += passo) {
      var y = y1 - (v / topo) * (y1 - y0);
      s += '<line class="grade" x1="' + x0 + '" x2="' + x1 + '" y1="' + y + '" y2="' + y + '"/>';
      s += '<text class="eixo" x="' + (x0 - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + fmt.n(v, dec) + "</text>";
    }
    if (unidade) s += '<text class="eixo" x="' + x0 + '" y="' + (y0 - 10) + '">' + fmt.esc(unidade) + "</text>";
    return { s: s, topo: topo };
  }

  var graf = {
    legenda: function (itens) {
      return '<div class="rp-leg">' + itens.map(function (i) {
        return '<span><i style="background:' + i.cor + (i.borda ? ";border:1px solid #9aa8a1" : "") + '"></i>' + fmt.esc(i.rotulo) + "</span>";
      }).join("") + "</div>";
    },

    // colunas empilhadas por ano. series: [{rotulo, cor, valores[]}] alinhadas a anos[]
    empilhado: function (el, o) {
      var anos = o.anos, n = anos.length, H = o.altura || 300;
      var x0 = 54, x1 = W - 10, y0 = 26, y1 = H - 30, larg = (x1 - x0) / n;
      var tot = anos.map(function (_, i) { return o.series.reduce(function (a, s) { return a + (s.valores[i] || 0); }, 0); });
      var ey = eixoY(o.max || Math.max.apply(null, tot), x0, x1, y0, y1, o.unidade);
      var s = ey.s;
      anos.forEach(function (ano, i) {
        var acc = 0, x = x0 + i * larg;
        o.series.forEach(function (se) {
          var v = se.valores[i] || 0; if (v <= 0) return;
          var h = (v / ey.topo) * (y1 - y0), y = y1 - ((acc + v) / ey.topo) * (y1 - y0);
          s += '<rect x="' + (x + 0.6) + '" y="' + y + '" width="' + Math.max(larg - 1.2, 0.8) + '" height="' + h + '" fill="' + se.cor + '"><title>' + ano + " · " + fmt.esc(se.rotulo) + ": " + fmt.n(v, o.dec === undefined ? 1 : o.dec) + " " + fmt.esc(o.unidade || "") + "</title></rect>";
          acc += v;
        });
        var cada = n > 30 ? 5 : n > 14 ? 2 : 1;
        if (rotular(i, n, cada)) s += '<text class="eixo" x="' + (x + larg / 2) + '" y="' + (y1 + 16) + '" text-anchor="middle">' + ano + "</text>";
      });
      (o.marcas || []).forEach(function (m) {
        var i = anos.indexOf(m.ano); if (i < 0) return;
        var x = x0 + (i + 0.5) * larg;
        s += '<line class="marca" x1="' + x + '" x2="' + x + '" y1="' + (y0 - 4) + '" y2="' + y1 + '" stroke="' + (m.cor || "#d98324") + '"/>';
        s += '<text class="val forte" x="' + (x + 4) + '" y="' + (y0 + 8) + '" fill="' + (m.cor || "#d98324") + '">' + fmt.esc(m.rotulo) + "</text>";
      });
      el.innerHTML = svg(H, s, o.rotulo) + (o.semLegenda ? "" : graf.legenda(o.series.filter(function (x) { return x.valores.some(function (v) { return v > 0; }); })));
    },

    // colunas simples. valores[] alinhados a x[]; cor por coluna opcional
    colunas: function (el, o) {
      var n = o.x.length, H = o.altura || 240;
      var x0 = 54, x1 = W - 10, y0 = 26, y1 = H - 30, larg = (x1 - x0) / n;
      var ey = eixoY(o.max || Math.max.apply(null, o.valores.concat([0.0001])), x0, x1, y0, y1, o.unidade), s = ey.s;
      o.x.forEach(function (rot, i) {
        var v = o.valores[i] || 0, h = (v / ey.topo) * (y1 - y0), x = x0 + i * larg;
        var cor = typeof o.cor === "function" ? o.cor(rot, i, v) : (o.cor || "#1f6f4a");
        if (v > 0) s += '<rect x="' + (x + 1) + '" y="' + (y1 - h) + '" width="' + Math.max(larg - 2, 1) + '" height="' + h + '" fill="' + cor + '"><title>' + fmt.esc(rot) + ": " + fmt.n(v, o.dec === undefined ? 1 : o.dec) + " " + fmt.esc(o.unidade || "") + "</title></rect>";
        var cada = n > 30 ? 5 : n > 14 ? 2 : 1;
        if (rotular(i, n, cada)) s += '<text class="eixo" x="' + (x + larg / 2) + '" y="' + (y1 + 16) + '" text-anchor="middle">' + fmt.esc(rot) + "</text>";
        if (o.rotular && v > 0) s += '<text class="val" x="' + (x + larg / 2) + '" y="' + (y1 - h - 5) + '" text-anchor="middle">' + fmt.n(v, o.dec === undefined ? 1 : o.dec) + "</text>";
      });
      (o.marcas || []).forEach(function (m) {
        var i = o.x.indexOf(m.x); if (i < 0) return;
        var x = x0 + (i + (m.antes ? 0 : 0.5)) * larg;
        s += '<line class="marca" x1="' + x + '" x2="' + x + '" y1="' + (y0 - 4) + '" y2="' + y1 + '" stroke="' + (m.cor || "#d98324") + '"/>';
        s += '<text class="val forte" x="' + (x + 4) + '" y="' + (y0 + 8) + '" fill="' + (m.cor || "#d98324") + '">' + fmt.esc(m.rotulo) + "</text>";
      });
      el.innerHTML = svg(H, s, o.rotulo) + (o.legenda ? graf.legenda(o.legenda) : "");
    },

    // barras horizontais. linhas: [{rotulo, valor, cor, texto, sub}]
    barrasH: function (el, o) {
      var L = o.linhas, alt = 30, H = 18 + L.length * alt, xr = o.xRotulo || 230, xmax = W - 110;
      var max = o.max || Math.max.apply(null, L.map(function (l) { return Math.abs(l.valor || 0); }).concat([0.0001]));
      var s = "";
      L.forEach(function (l, i) {
        var y = 12 + i * alt, w = Math.max(0, (Math.abs(l.valor || 0) / max) * (xmax - xr));
        s += '<text class="rot' + (l.forte ? " forte" : "") + '" x="0" y="' + (y + 15) + '">' + fmt.esc(l.rotulo) + "</text>";
        if (l.sub) s += '<text class="rot sub" x="0" y="' + (y + 27) + '">' + fmt.esc(l.sub) + "</text>";
        s += '<rect class="trilho" x="' + xr + '" y="' + (y + 4) + '" width="' + (xmax - xr) + '" height="14" rx="2"/>';
        s += '<rect x="' + xr + '" y="' + (y + 4) + '" width="' + w + '" height="14" rx="2" fill="' + (l.cor || "#1f6f4a") + '"/>';
        s += '<text class="val' + (l.forte ? " forte" : "") + '" x="' + (xmax + 8) + '" y="' + (y + 16) + '">' + fmt.esc(l.texto !== undefined ? l.texto : fmt.n(l.valor, 1)) + "</text>";
      });
      el.innerHTML = svg(H, s, o.rotulo);
    },

    // linhas no tempo. series: [{rotulo, cor, valores[], tracejado}]; faixa: {min[], max[], cor}
    linhas: function (el, o) {
      var n = o.x.length, H = o.altura || 260, x0 = 54, x1 = W - 14, y0 = 26, y1 = H - 30;
      var todos = [];
      o.series.forEach(function (se) { se.valores.forEach(function (v) { if (!vazio(v)) todos.push(v); }); });
      if (o.faixa) o.faixa.max.forEach(function (v) { if (!vazio(v)) todos.push(v); });
      var vmin = o.min !== undefined ? o.min : Math.min.apply(null, todos), vmax = o.max !== undefined ? o.max : Math.max.apply(null, todos);
      var folga = (vmax - vmin) * 0.12 || 1;
      if (o.min === undefined) vmin -= folga;
      if (o.max === undefined) vmax += folga;
      var py = function (v) { return y1 - ((v - vmin) / (vmax - vmin || 1)) * (y1 - y0); };
      var px = function (i) { return x0 + (n === 1 ? 0.5 : i / (n - 1)) * (x1 - x0); };
      var s = "", passo = passoEixo(vmax - vmin), t0 = Math.ceil(vmin / passo) * passo;
      for (var v = t0; v <= vmax + 1e-9; v += passo) {
        s += '<line class="grade" x1="' + x0 + '" x2="' + x1 + '" y1="' + py(v) + '" y2="' + py(v) + '"/>';
        s += '<text class="eixo" x="' + (x0 - 6) + '" y="' + (py(v) + 4) + '" text-anchor="end">' + fmt.n(v, casas(passo)) + "</text>";
      }
      if (o.unidade) s += '<text class="eixo" x="' + x0 + '" y="' + (y0 - 10) + '">' + fmt.esc(o.unidade) + "</text>";
      var cada = n > 30 ? 5 : n > 14 ? 2 : 1;
      o.x.forEach(function (rot, i) { if (rotular(i, n, cada)) s += '<text class="eixo" x="' + px(i) + '" y="' + (y1 + 16) + '" text-anchor="middle">' + fmt.esc(rot) + "</text>"; });
      if (o.faixa) {
        var cima = o.faixa.max.map(function (v, i) { return px(i) + "," + py(v); }), baixo = o.faixa.min.map(function (v, i) { return px(i) + "," + py(v); }).reverse();
        s += '<polygon class="faixa" fill="' + (o.faixa.cor || "#1f6f4a") + '" points="' + cima.concat(baixo).join(" ") + '"/>';
      }
      o.series.forEach(function (se) {
        var pts = [];
        se.valores.forEach(function (v, i) { if (!vazio(v)) pts.push(px(i) + "," + py(v)); });
        s += '<polyline fill="none" stroke="' + se.cor + '" stroke-width="' + (se.espessura || 2) + '"' + (se.tracejado ? ' stroke-dasharray="5 4"' : "") + ' points="' + pts.join(" ") + '"/>';
        if (se.pontos) se.valores.forEach(function (v, i) { if (!vazio(v)) s += '<circle cx="' + px(i) + '" cy="' + py(v) + '" r="2.4" fill="' + se.cor + '"><title>' + fmt.esc(o.x[i]) + ": " + fmt.n(v, o.dec === undefined ? 1 : o.dec) + "</title></circle>"; });
      });
      (o.marcas || []).forEach(function (m) {
        var i = o.x.indexOf(m.x); if (i < 0) return;
        s += '<line class="marca" x1="' + px(i) + '" x2="' + px(i) + '" y1="' + (y0 - 4) + '" y2="' + y1 + '" stroke="' + (m.cor || "#d98324") + '"/>';
        s += '<text class="val forte" x="' + (px(i) + 4) + '" y="' + (y0 + 8) + '" fill="' + (m.cor || "#d98324") + '">' + fmt.esc(m.rotulo) + "</text>";
      });
      el.innerHTML = svg(H, s, o.rotulo) + (o.semLegenda ? "" : graf.legenda(o.series.map(function (x) { return { rotulo: x.rotulo, cor: x.cor }; })));
    },

    // Sankey de duas colunas. esq/dir: [{id, rotulo, cor}], fluxos: [{de, para, valor}]
    sankey: function (el, o) {
      // rótulos dos dois lados: "Formação Florestal · 145.079" pede ~190 px
      var H = o.altura || 340, xa = 190, xb = W - 206, lw = 16, gap = 8, y0 = 30, y1 = H - 8;
      function totais(lado, chave) {
        return lado.map(function (n) { return { n: n, v: o.fluxos.filter(function (f) { return f[chave] === n.id; }).reduce(function (a, f) { return a + f.valor; }, 0) }; }).filter(function (t) { return t.v > 0; });
      }
      var A = totais(o.esq, "de"), B = totais(o.dir, "para");
      var soma = A.reduce(function (a, t) { return a + t.v; }, 0) || 1;
      var esc = function (lado) { return (y1 - y0 - gap * (lado.length - 1)) / soma; };
      var ka = esc(A), kb = esc(B), k = Math.min(ka, kb);
      function posicionar(lado) { var y = y0, m = {}; lado.forEach(function (t) { m[t.n.id] = { y: y, h: t.v * k, off: 0, t: t }; y += t.v * k + gap; }); return m; }
      var PA = posicionar(A), PB = posicionar(B), s = "";
      s += '<text class="cab" x="' + xa + '" y="16" text-anchor="end">' + fmt.esc(o.rotuloEsq || "") + '</text><text class="cab" x="' + xb + '" y="16">' + fmt.esc(o.rotuloDir || "") + "</text>";
      o.fluxos.slice().sort(function (a, b) { return b.valor - a.valor; }).forEach(function (f) {
        var a = PA[f.de], b = PB[f.para]; if (!a || !b || f.valor <= 0) return;
        var h = f.valor * k, ya = a.y + a.off, yb = b.y + b.off; a.off += h; b.off += h;
        var mx = (xa + lw + xb) / 2, cor = (a.t.n.cor || "#9aa8a1");
        s += '<path d="M' + (xa + lw) + "," + (ya + h / 2) + " C" + mx + "," + (ya + h / 2) + " " + mx + "," + (yb + h / 2) + " " + xb + "," + (yb + h / 2) + '" stroke="' + cor + '" stroke-opacity="' + (f.de === f.para ? 0.28 : 0.55) + '" stroke-width="' + Math.max(h, 0.6) + '" fill="none"><title>' + fmt.esc(a.t.n.rotulo) + " → " + fmt.esc(b.t.n.rotulo) + ": " + fmt.n(f.valor, 1) + " " + fmt.esc(o.unidade || "ha") + "</title></path>";
      });
      [[A, PA, xa, "end", -6], [B, PB, xb, "start", lw + 6]].forEach(function (L) {
        L[0].forEach(function (t) {
          var p = L[1][t.n.id];
          s += '<rect x="' + L[2] + '" y="' + p.y + '" width="' + lw + '" height="' + Math.max(p.h, 1) + '" fill="' + (t.n.cor || "#9aa8a1") + '" stroke="#fff" stroke-width=".5"/>';
          if (p.h >= 9) s += '<text class="rot sub" x="' + (L[2] + L[4]) + '" y="' + (p.y + p.h / 2 + 4) + '" text-anchor="' + L[3] + '">' + fmt.esc(t.n.rotulo) + " · " + fmt.n(t.v, t.v < 100 ? 1 : 0) + "</text>";
        });
      });
      el.innerHTML = svg(H, s, o.rotulo);
    },

    // tabela. colunas: [{rotulo, n:bool}], linhas: [[celula...]] (HTML já escapado pelo chamador)
    tabela: function (el, o) {
      var h = '<table class="rp-tab"><thead><tr>' + o.colunas.map(function (c) { return '<th' + (c.n ? ' class="n"' : "") + ">" + fmt.esc(c.rotulo) + "</th>"; }).join("") + "</tr></thead><tbody>";
      o.linhas.forEach(function (l) { h += "<tr>" + l.map(function (c, i) { return '<td' + (o.colunas[i] && o.colunas[i].n ? ' class="n"' : "") + ">" + c + "</td>"; }).join("") + "</tr>"; });
      el.innerHTML = h + "</tbody></table>" + (o.nota ? '<p class="rp-fig-legenda">' + o.nota + "</p>" : "");
    },
    qd: function (cor) { return '<span class="qd" style="background:' + cor + '"></span>'; }
  };

  // ─── utilidades ─────────────────────────────────────────────────────────
  function carregarLeaflet() {
    if (!document.getElementById("rp-leaflet-css")) {
      var l = document.createElement("link");
      l.id = "rp-leaflet-css"; l.rel = "stylesheet"; l.href = LEAFLET_CSS; l.integrity = LEAFLET_CSS_SRI; l.crossOrigin = "";
      document.head.appendChild(l);
    }
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (window.__rpLeaflet) return window.__rpLeaflet;
    window.__rpLeaflet = new Promise(function (ok, falha) {
      var s = document.createElement("script");
      s.src = LEAFLET_JS; s.integrity = LEAFLET_JS_SRI; s.crossOrigin = "";
      s.onload = function () { ok(window.L); };
      s.onerror = function () { window.__rpLeaflet = null; falha(new Error("Leaflet não carregou")); };
      document.head.appendChild(s);
    });
    return window.__rpLeaflet;
  }

  // Mesma regra do getBackendURL do Reflex: um backend em "localhost" é o
  // próprio host da página (single-port em produção); em https, sem porta.
  function urlBackend(base) {
    if (!base) return window.location.origin;
    try {
      var u = new URL(base);
      if (["localhost", "0.0.0.0", "::", "0:0:0:0:0:0:0:0"].indexOf(u.hostname) >= 0) {
        u.hostname = window.location.hostname;
        if (window.location.protocol === "https:") { u.protocol = "https:"; u.port = ""; }
      }
      return u.origin;
    } catch (e) { return window.location.origin; }
  }

  function esperar(sel, ms) {
    return new Promise(function (ok, falha) {
      var t0 = Date.now();
      (function olhar() {
        var el = document.querySelector(sel);
        if (el && !el.dataset.rpIniciada) return ok(el);
        if (Date.now() - t0 > ms) return falha(new Error("raiz ausente"));
        setTimeout(olhar, 80);
      })();
    });
  }

  function limites(L, alvo) {
    if (!alvo) return null;
    if (Array.isArray(alvo)) return L.latLngBounds(alvo);
    try { var b = L.geoJSON(alvo).getBounds(); return b.isValid() ? b : null; } catch (e) { return null; }
  }

  // o rótulo de cada selo, pela língua da página (a classe CSS não muda)
  var SELO = { real: ["real", "measured"], declarado: ["declarado", "declared"], estimado: ["estimado", "estimated"],
               ausente: ["ausente", "missing"], exemplo: ["exemplo", "example"], print: ["print", "screenshot"] };

  // ─── motor ──────────────────────────────────────────────────────────────
  function iniciar(cfg) {
    esperar(cfg.raiz || "#rp-raiz", 15000).then(function (raiz) {
      raiz.dataset.rpIniciada = "1";
      montar(raiz, cfg);
    }).catch(function () { /* página sem demonstração: nada a fazer */ });
  }

  function montar(raiz, cfg) {
    var $ = function (s) { return raiz.querySelector(s); };
    var $$ = function (s) { return Array.prototype.slice.call(raiz.querySelectorAll(s)); };
    var estado = $("#rp-fig-estado"), area = $(".rp-fig-area"), legMapa = $("#rp-mapa-legenda");
    // a língua da página: <div id="rp-raiz" lang="en"> → textos e números em inglês
    var lang = (raiz.getAttribute("lang") || "pt").slice(0, 2) === "en" ? "en" : "pt";
    LOCALE = lang === "en" ? "en-US" : "pt-BR";
    var ctx = {
      lang: lang,
      // um texto nas duas línguas, escolhido pela página: ctx.t("…", "…")
      t: function (pt, en) { return lang === "en" ? en : pt; },
      raiz: raiz, $: $, $$: $$, fmt: fmt, graf: graf, dados: null, L: null, mapa: null,
      backend: urlBackend(raiz.dataset.backend), params: new URLSearchParams(window.location.search),
      _tiles: {}, _imagens: {}, _vetores: {}, _passo: null
    };

    ctx.preencher = function (campos) {
      Object.keys(campos).forEach(function (k) {
        $$('[data-campo="' + k + '"]').forEach(function (el) { el.innerHTML = campos[k]; });
      });
    };
    ctx.texto = function (id, html) { var el = $("#t-" + id); if (el) el.innerHTML = html || ""; };
    ctx.legendaMapa = function (html) { if (legMapa) legMapa.innerHTML = html || ""; };
    ctx.legendaFig = function (html) { var el = $("#rp-fig-legenda"); if (el) el.innerHTML = html || ""; };

    // tiles: {chave: {url, opacity, attribution, z}} — o que não estiver no objeto sai do mapa
    ctx.tiles = function (pedidas) {
      if (!ctx.mapa) return;
      pedidas = pedidas || {};
      Object.keys(ctx._tiles).forEach(function (k) {
        if (!pedidas[k]) { ctx.mapa.removeLayer(ctx._tiles[k]); delete ctx._tiles[k]; }
      });
      Object.keys(pedidas).forEach(function (k) {
        var p = pedidas[k]; if (!p || !p.url) return;
        if (ctx._tiles[k]) { ctx._tiles[k].setOpacity(p.opacity === undefined ? 0.85 : p.opacity); return; }
        var op = {
          opacity: p.opacity === undefined ? 0.85 : p.opacity, zIndex: p.z || 10,
          attribution: p.attribution || "", maxNativeZoom: p.maxNativeZoom || 18, maxZoom: 20
        };
        // WMS (ex.: imóveis do SICAR): {url, layers, format, transparent, version}
        ctx._tiles[k] = (p.layers
          ? ctx.L.tileLayer.wms(p.url, Object.assign(op, { layers: p.layers, format: p.format || "image/png", transparent: p.transparent !== false, version: p.version || "1.1.1" }))
          : ctx.L.tileLayer(p.url, op)).addTo(ctx.mapa);
      });
    };
    // imagens: {chave: {url, bounds: [[sul, oeste], [norte, leste]], opacity, attribution}} — idem.
    // Para páginas estáticas (as histórias do portal), onde os tiles do Earth Engine
    // expirariam: a camada vem pré-renderizada como PNG recortado na área da página.
    ctx.imagens = function (pedidas) {
      if (!ctx.mapa) return;
      pedidas = pedidas || {};
      Object.keys(ctx._imagens).forEach(function (k) {
        if (!pedidas[k]) { ctx.mapa.removeLayer(ctx._imagens[k]); delete ctx._imagens[k]; }
      });
      Object.keys(pedidas).forEach(function (k) {
        var p = pedidas[k]; if (!p || !p.url || !p.bounds) return;
        var op = p.opacity === undefined ? 0.85 : p.opacity;
        if (ctx._imagens[k]) { ctx._imagens[k].setOpacity(op); return; }
        ctx._imagens[k] = ctx.L.imageOverlay(p.url, p.bounds, { opacity: op, attribution: p.attribution || "", zIndex: p.z || 10 }).addTo(ctx.mapa);
      });
    };
    // vetores: {chave: {geojson, estilo, ponto, popup}} — idem
    ctx.vetores = function (pedidos) {
      if (!ctx.mapa) return;
      pedidos = pedidos || {};
      Object.keys(ctx._vetores).forEach(function (k) {
        if (!pedidos[k]) { ctx.mapa.removeLayer(ctx._vetores[k]); delete ctx._vetores[k]; }
      });
      Object.keys(pedidos).forEach(function (k) {
        var p = pedidos[k]; if (!p || !p.geojson) return;
        if (ctx._vetores[k]) { if (p.estilo && ctx._vetores[k].setStyle) ctx._vetores[k].setStyle(p.estilo); return; }
        ctx._vetores[k] = ctx.L.geoJSON(p.geojson, {
          pane: "rpVetores", interactive: !!p.popup,
          // o Leaflet aplica style também aos circleMarkers; sem estilo próprio, um
          // ponto fica com o seu "ponto" em vez de virar um anel laranja vazio
          style: function (f) {
            if (typeof p.estilo === "function") return p.estilo(f);
            if (p.estilo) return p.estilo;
            return f && f.geometry && f.geometry.type === "Point" ? {} : { color: "#ffb020", weight: 2, fillOpacity: 0 };
          },
          pointToLayer: function (f, ll) { return ctx.L.circleMarker(ll, typeof p.ponto === "function" ? p.ponto(f) : (p.ponto || { radius: 5, color: "#fff", weight: 1.5, fillColor: "#d98324", fillOpacity: 1 })); },
          onEachFeature: p.popup ? function (f, l) { var h = p.popup(f); if (h) l.bindTooltip(h, { sticky: true }); } : undefined
        }).addTo(ctx.mapa);
      });
    };
    ctx.enquadrar = function (alvo, opcoes) {
      if (!ctx.mapa) return;
      var b = limites(ctx.L, alvo);
      if (b) ctx.mapa.flyToBounds(b, Object.assign({ padding: [24, 24], maxZoom: 15, duration: 0.8 }, opcoes || {}));
    };
    ctx.centro = function (latlon, zoom) { if (ctx.mapa) ctx.mapa.flyTo(latlon, zoom, { duration: 0.8 }); };

    function ativar(passo) {
      if (!passo || passo === ctx._passo) return;
      ctx._passo = passo;
      if (ctx.travarMapa) ctx.travarMapa();
      $$(".rp-passo").forEach(function (p) { p.classList.toggle("ativo", p === passo); });
      var id = passo.dataset.passo;
      var camada = passo.dataset.camada !== undefined ? passo.dataset.camada : id;
      $$(".rp-camada").forEach(function (c) { c.classList.toggle("ativa", !!camada && c.id === "camada-" + camada); });
      var blocos = (passo.dataset.bloco || "").split(",").map(function (b) { return b.trim(); });
      $$(".pg-b").forEach(function (b) { b.classList.toggle("aceso", blocos.indexOf(b.dataset.bloco) >= 0); });
      var tit = $("#rp-fig-titulo"); if (tit && passo.dataset.titulo) tit.textContent = passo.dataset.titulo;
      var selo = $("#rp-fig-selo");
      if (selo) {
        var sv = passo.dataset.selo || "";
        selo.className = "selo " + sv;
        selo.textContent = (SELO[sv] || [sv, sv])[ctx.lang === "en" ? 1 : 0];
        selo.style.display = sv ? "" : "none";
      }
      var url = $("#rp-fig-url"); if (url && passo.dataset.url) url.textContent = passo.dataset.url;
      if (area) {
        area.dataset.mapa = passo.dataset.mapa || "grande";
        // agora, antes do tratador enquadrar: um mapa que estava oculto (0×0)
        // faria o fitBounds calcular o zoom máximo; e de novo depois da animação
        if (ctx.mapa) { ctx.mapa.invalidateSize(false); setTimeout(function () { ctx.mapa.invalidateSize(); }, 30); }
      }
      ctx.legendaFig("");
      if (!ctx.dados) return;
      var fn = cfg.passos && cfg.passos[id];
      if (fn) { try { fn(ctx, ctx.dados); } catch (e) { console.error("[reportagem] passo " + id, e); } }
    }
    ctx.reativar = function () { var p = ctx._passo; ctx._passo = null; ativar(p); };

    // notas: o botão abre o <li id="nota-N"> da lista do fim num pop-up junto
    // dele; um clique fora, Esc ou rolar a página fecha. A lista continua lá
    // para quem imprime, usa leitor de tela ou está no celular.
    var pop = document.createElement("div");
    pop.className = "rp-pop"; pop.hidden = true; pop.setAttribute("role", "note");
    raiz.appendChild(pop);
    var fecharNota = function () { pop.hidden = true; };
    raiz.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".rp-nota");
      if (!b) { if (!e.target.closest || !e.target.closest(".rp-pop")) fecharNota(); return; }
      var li = raiz.querySelector("#nota-" + b.dataset.nota);
      if (!li) return;
      e.preventDefault();
      pop.innerHTML = li.innerHTML;
      pop.hidden = false;
      var r = b.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
      pop.style.left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left - 20)) + "px";
      pop.style.top = (r.bottom + h + 12 < window.innerHeight ? r.bottom + 8 : Math.max(12, r.top - h - 8)) + "px";
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") fecharNota(); });
    raiz.addEventListener("scroll", fecharNota, { passive: true });

    // quem está no meio da janela de rolagem é o passo ativo. No celular a
    // figura ocupa a metade de cima (kit.css), então o passo acende ainda na
    // metade de baixo, antes de o cartão subir por cima da figura.
    var celular = window.matchMedia("(max-width: 900px)").matches;
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) { if (e.isIntersecting) ativar(e.target); });
    }, { root: raiz, rootMargin: celular ? "-64% 0px -30% 0px" : "-45% 0px -45% 0px", threshold: 0 });
    $$(".rp-passo").forEach(function (p) { obs.observe(p); });

    var urlDados = typeof cfg.dados === "function" ? cfg.dados(ctx) : cfg.dados;
    if (urlDados && urlDados.charAt(0) === "/") urlDados = ctx.backend + urlDados;

    var mapaPronto = carregarLeaflet().then(function (L) {
      ctx.L = L;
      var el = $("#rp-mapa"); if (!el) return;
      ctx.mapa = L.map(el, { zoomControl: true, scrollWheelZoom: false, attributionControl: true, worldCopyJump: true })
        .setView(cfg.centro || [-14, -52], cfg.zoom || 4);
      ctx.mapa.createPane("rpVetores").style.zIndex = 450;
      var base = cfg.base || { url: "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attribution: "© Google" };
      L.tileLayer(base.url, { attribution: base.attribution, maxZoom: 20, maxNativeZoom: base.maxNativeZoom || 20 }).addTo(ctx.mapa);
      // rolar a página não deve dar zoom; clicar no mapa libera
      ctx.mapa.on("click", function () { ctx.mapa.scrollWheelZoom.enable(); });
      ctx.mapa.on("mouseout", function () { ctx.mapa.scrollWheelZoom.disable(); });
      // No toque, o mapa fixo ocupa a metade de cima da tela: com arrasto ligado
      // o Leaflet põe touch-action:none e o dedo que rola a página passa a mover
      // o mapa (medido em 390×844: um gesto de 250 px rolava 0 px; travado, rola 253). Então ele começa
      // travado, um toque libera arrastar e pinçar, e o passo seguinte trava de novo.
      if (window.matchMedia("(pointer: coarse)").matches) {
        var caixaMapa = el.parentElement;
        ctx.travarMapa = function () {
          ctx.mapa.dragging.disable(); ctx.mapa.touchZoom.disable();
          if (caixaMapa) caixaMapa.classList.add("rp-mapa-travado");
        };
        ctx.travarMapa();
        ctx.mapa.on("click", function () {
          ctx.mapa.dragging.enable(); ctx.mapa.touchZoom.enable();
          if (caixaMapa) caixaMapa.classList.remove("rp-mapa-travado");
        });
        if (caixaMapa) caixaMapa.setAttribute("data-dica", ctx.t("toque no mapa para mover e dar zoom", "tap the map to pan and zoom"));
      }
    }).catch(function (e) {
      if (estado) estado.textContent = ctx.t("O mapa não carregou (" + e.message + "). Os números continuam valendo.",
                                             "The map did not load (" + e.message + "). The numbers still stand.");
    });

    var pedido = urlDados
      ? fetch(urlDados, { credentials: "omit" }).then(function (r) {
          return r.json().then(function (j) { if (!r.ok) throw new Error(j && (j.detail || j.error) || ("HTTP " + r.status)); return j; });
        })
      : Promise.resolve({});

    Promise.all([pedido, mapaPronto]).then(function (res) {
      ctx.dados = res[0];
      if (estado) estado.textContent = "";
      if (cfg.aoCarregar) { try { cfg.aoCarregar(ctx, ctx.dados); } catch (e) { console.error("[reportagem] aoCarregar", e); } }
      ctx.reativar();
      if (!ctx._passo) ativar($(".rp-passo"));
    }).catch(function (e) {
      if (estado) { estado.classList.add("erro"); estado.textContent = ctx.t("Não foi possível carregar o exemplo: ", "The example could not be loaded: ") + e.message; }
      if (cfg.aoFalhar) cfg.aoFalhar(ctx, e);
    });
  }

  window.Reportagem = { iniciar: iniciar, fmt: fmt, graf: graf };
})();
