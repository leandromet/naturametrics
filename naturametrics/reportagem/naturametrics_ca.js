/* Naturametrics — the Canada walkthrough (/walkthrough, a point above Kelowna).
 *
 * The numbers come from /_demonstracao/naturametrics_ca.json
 * (canada/services/demonstracao.py), built by the Canada page's own services.
 * This file only decides what each step shows; no value is written by hand.
 * English only: the Portuguese walkthrough opens a Brazilian plot
 * (naturametrics.js).
 */
(function () {
  var R = window.Reportagem, fmt = R.fmt, graf = R.graf;

  var COR_RAIO = { "0.5": "#d98324", "1": "#b5651d", "2": "#1f6f4a", "5": "#4f8f6f", "10": "#9cc2ac" };
  var PONTO = { radius: 6, color: "#fff", weight: 2, fillColor: "#d98324", fillOpacity: 1 };

  function rot(r) { return fmt.n(Number(r), Number(r) < 1 ? 1 : 0) + " km"; }
  function areaDisco(r) { return Math.PI * Number(r) * Number(r) * 100; }   // ha
  function circulo(lat, lon, km) {
    var pts = [], dlat = km / 110.574, dlon = km / (111.32 * Math.cos(lat * Math.PI / 180));
    for (var i = 0; i <= 96; i++) { var a = (i / 96) * 2 * Math.PI; pts.push([lon + dlon * Math.cos(a), lat + dlat * Math.sin(a)]); }
    return { type: "Feature", properties: { r: String(km) }, geometry: { type: "Polygon", coordinates: [pts] } };
  }
  function pontoGeo(d) { return { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [d.ponto.lon, d.ponto.lat] } }; }
  function disco(d, r) { return circulo(d.ponto.lat, d.ponto.lon, Number(r)); }
  function vet(d, raios) {
    var v = { ponto: { geojson: pontoGeo(d), ponto: PONTO } };
    if (raios) v.discos = { geojson: { type: "FeatureCollection", features: raios.map(function (r) { return disco(d, r); }) },
      estilo: function (f) { return { color: COR_RAIO[f.properties.r] || "#ffd400", weight: 2, dashArray: "5 4", fillOpacity: 0 }; } };
    return v;
  }
  function classesNoAno(d, r, i) {
    var h = d.historico, z = h.raios[r] || {};
    return Object.keys(z).map(function (c) { return { id: c, ha: z[c][i] || 0, nome: h.classes[c].nome_en || h.classes[c].nome, cor: h.classes[c].cor }; })
      .filter(function (x) { return x.ha > 0; }).sort(function (a, b) { return b.ha - a.ha; });
  }
  function nativaPct(d, r) {
    var h = d.historico, z = h.raios[r] || {}, nat = h.nativas.map(String);
    return h.anos.map(function (_, i) {
      var tot = 0, n = 0;
      Object.keys(z).forEach(function (c) { tot += z[c][i] || 0; if (nat.indexOf(c) >= 0) n += z[c][i] || 0; });
      return tot > 0 ? (100 * n) / tot : null;
    });
  }
  function camada(d, k, op) { var c = d.camadas[k]; return c ? Object.assign({}, c, op ? { opacity: op } : {}) : null; }
  function faltou(el, nome) {
    el.innerHTML = '<p class="rp-fig-estado erro">' + nome + ' did not respond this time <span class="selo ausente">missing</span></p>';
  }
  // the age summary counts forested pixels only; the share of the disc comes from the disc's own area
  function florestaPct(d, r) { var s = d.idade && d.idade.resumo[r]; return s ? 100 * s.forest_area_ha / areaDisco(r) : null; }
  function piorAno(d) { return (d.perda || []).slice().sort(function (a, b) { return b.ha - a.ha; })[0]; }

  R.iniciar({
    dados: function (ctx) {
      var lat = parseFloat(ctx.params.get("lat")), lon = parseFloat(ctx.params.get("lon"));
      return "/_demonstracao/naturametrics_ca.json" + (isFinite(lat) && isFinite(lon) ? "?lat=" + lat + "&lon=" + lon : "");
    },
    centro: [49.825, -119.35], zoom: 11,

    aoCarregar: function (ctx, d) {
      var rp = d.raio_principal, ip = d.idade_ponto, m = d.mudanca && d.mudanca.raios[rp], pior = piorAno(d);
      ctx.preencher({
        "n-idade": ip && ip.is_forest ? ip.age + " years" : "not forest",
        "n-floresta": florestaPct(d, rp) === null ? "—" : fmt.pct(florestaPct(d, rp)),
        "n-floresta-rot": "of the " + rot(rp) + ' circle is forest (NTEMS, 2019) <span class="selo estimado">estimated</span>',
        "n-perda": m ? fmt.ha(m.loss_ha) : "—",
        "n-perda-rot": "of tree cover lost within " + rot(rp) + ' since 2001 (Hansen) <span class="selo real">measured</span>',
        "n-pior": pior ? String(pior.ano) : "—",
        "n-pior-rot": pior ? "the worst year for loss within " + rot(rp) + ": " + fmt.ha(pior.ha) + ' <span class="selo real">measured</span>' : "the worst year for loss"
      });
      var p = d.ponto, app = "/canada?lat=" + p.lat + "&lon=" + p.lon + "&lang=en";
      ctx.$("#link-app").href = app; ctx.$("#cta-app").href = app;
      ctx.$("#rp-fig-url").textContent = "naturametrics.umaterra.com.br" + app;
      ctx.$("#topo-exemplo").textContent = fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4);
      ctx.$("#abertura-exemplo").innerHTML = (d.exemplo_padrao ? "This page's example: a conifer stand on the lower slopes of Myra-Bellevue, above the East Kelowna orchards, " : "Chosen point: ") +
        "<b>" + fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4) + "</b>, computed by the app's services on " + fmt.dataHora(d.gerado_em) +
        (d.exemplo_padrao ? " and stored with this page." : " (the result is kept for a few hours).");
      var erros = Object.keys(d.erros || {});
      ctx.$("#fim-extra").innerHTML = erros.length
        ? "These did not respond this time: <b>" + erros.map(fmt.esc).join(", ") + "</b>. The matching steps say what is missing."
        : "Every analysis responded in the run of " + fmt.dataHora(d.gerado_em) + ".";
      ctx.texto("ponto", "Here the point falls at " + fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4) + ". " +
        (ip && ip.is_forest ? "Its pixel is forest, a stand NTEMS dates to about <b>" + ip.age + " years</b> old in " + ip.reference_year + "." : "Its pixel is not forest in NTEMS."));
      var h = d.historico;
      if (h) {
        var i = h.anos.length - 1, a = classesNoAno(d, "0.5", i)[0], b = classesNoAno(d, "10", i);
        ctx.texto("discos", "In the 0.5 km circle, the largest class in " + h.anos[i] + " is <b>" + fmt.esc(a ? a.nome.toLowerCase() : "—") +
          "</b>; in the 10 km circle there are " + b.length + " classes, led by " + b.slice(0, 3).map(function (c) { return "<b>" + fmt.esc(c.nome.toLowerCase()) + "</b>"; }).join(", ") + ".");
      }
    },

    passos: {
      ponto: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores(vet(d));
        ctx.centro([d.ponto.lat, d.ponto.lon], 14);
        ctx.legendaMapa('<span><i style="background:#d98324"></i>the point</span>');
        var ip = d.idade_ponto;
        ctx.$("#fig-ponto").innerHTML = '<dl class="rp-ficha"><dt>Latitude</dt><dd>' + fmt.n(d.ponto.lat, 5) + "</dd><dt>Longitude</dt><dd>" + fmt.n(d.ponto.lon, 5) +
          "</dd><dt>Stand age (2019)</dt><dd>" + (ip && ip.is_forest ? ip.age + " years" : "not forest") + "</dd><dt>Circles</dt><dd>" + d.raios.map(rot).join(" · ") + "</dd></dl>";
      },

      discos: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores(vet(d, d.raios));
        ctx.enquadrar(disco(d, d.raios[d.raios.length - 1]), { maxZoom: 13 });
        ctx.legendaMapa(d.raios.map(function (r) { return '<span><i style="background:' + COR_RAIO[r] + '"></i>' + rot(r) + "</span>"; }).join(""));
        graf.tabela(ctx.$("#fig-discos"), {
          colunas: [{ rotulo: "Circle" }, { rotulo: "Area", n: true }, { rotulo: "30 m pixels", n: true }],
          linhas: d.raios.map(function (r) { return [graf.qd(COR_RAIO[r]) + rot(r), fmt.ha(areaDisco(r)), fmt.n(areaDisco(r) / 0.09, 0)]; })
        });
      },

      historia: function (ctx, d) {
        var el = ctx.$("#fig-historia"), h = d.historico, rp = d.raio_principal;
        if (!h) return faltou(el, "The crop inventory");
        var ultimo = h.anos[h.anos.length - 1];
        ctx.tiles({ aci: camada(d, "aci_" + ultimo, 0.8) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa("<b>AAFC crop inventory " + ultimo + "</b>" + classesNoAno(d, rp, h.anos.length - 1).slice(0, 6).map(function (c) { return '<span><i style="background:' + c.cor + '"></i>' + fmt.esc(c.nome) + "</span>"; }).join(""));
        var z = h.raios[rp];
        var series = Object.keys(z).map(function (c) { return { rotulo: h.classes[c].nome_en || h.classes[c].nome, cor: h.classes[c].cor, valores: z[c] }; })
          .filter(function (s) { return s.valores.some(function (v) { return v > 1; }); })
          .sort(function (a, b) { return b.valores[b.valores.length - 1] - a.valores[a.valores.length - 1]; });
        graf.empilhado(el, { anos: h.anos, series: series, unidade: "ha" });
        var cf = classesNoAno(d, rp, h.anos.length - 1), c0 = classesNoAno(d, rp, 0);
        var antes = function (id) { var x = c0.filter(function (c) { return c.id === id; })[0]; return x ? x.ha : 0; };
        var novo = cf.filter(function (c) { return antes(c.id) < 1 && c.ha > 50; })[0];
        ctx.texto("historia", "In the " + rot(rp) + " circle, " + ultimo + ": " + cf.slice(0, 3).map(function (c) { return "<b>" + fmt.esc(c.nome.toLowerCase()) + "</b> " + fmt.ha(c.ha); }).join(", ") + ". " +
          (novo ? "<b>" + fmt.esc(novo.nome) + "</b> go from nothing in " + h.anos[0] + " to " + fmt.ha(novo.ha) + ": in a valley planted with orchards for a century, that is far more likely the inventory learning to see the class than a planting boom. Read a class's first years with care." : ""));
      },

      raios: function (ctx, d) {
        var el = ctx.$("#fig-raios"), h = d.historico;
        if (!h) return faltou(el, "The crop inventory");
        ctx.tiles({ aci: camada(d, "aci_" + h.anos[0], 0.8) });
        ctx.vetores(vet(d, d.raios));
        ctx.enquadrar(disco(d, "10"), { maxZoom: 13 });
        ctx.legendaMapa("<b>AAFC crop inventory " + h.anos[0] + "</b>" + d.raios.map(function (r) { return '<span><i style="background:' + COR_RAIO[r] + '"></i>' + rot(r) + "</span>"; }).join(""));
        var series = d.raios.map(function (r) { return { rotulo: rot(r), cor: COR_RAIO[r], valores: nativaPct(d, r), espessura: r === "0.5" ? 3 : 2 }; });
        graf.linhas(el, { x: h.anos, series: series, unidade: "% natural vegetation", min: 0, max: 100 });
        var n = h.anos.length - 1, p = series[0].valores[n], f = series[series.length - 1].valores[n];
        ctx.texto("raios", "In " + h.anos[n] + ", natural vegetation is <b>" + fmt.pct(p) + "</b> of the 0.5 km circle and <b>" + fmt.pct(f) + "</b> of the 10 km circle. " +
          (p - f > 15 ? "The point sits in a forest that thins out towards the valley floor, where orchards and suburbs take over." : "Near and far look alike here."));
      },

      pixel: function (ctx, d) {
        var el = ctx.$("#fig-pixel"), px = d.pixel;
        if (!px || !px.length) return faltou(el, "The point's pixel");
        ctx.tiles({ aci: camada(d, "aci_" + px[px.length - 1].ano, 0.85) });
        ctx.vetores(vet(d));
        ctx.centro([d.ponto.lat, d.ponto.lon], 16);
        ctx.legendaMapa("<b>The 30 m pixel under the point</b>");
        el.innerHTML = '<div class="rp-caixa-tit">Crop-inventory class of the point\'s pixel, year by year</div><div style="display:flex;flex-wrap:wrap;gap:3px">' +
          px.map(function (x) { return '<div title="' + fmt.esc(x.nome_en) + '" style="flex:1 0 44px;text-align:center;font:600 10.5px var(--rp-sans);padding:5px 2px;border-radius:3px;color:#fff;background:' + x.cor + '">' + x.ano + "</div>"; }).join("") + "</div>";
        var classes = {}; px.forEach(function (x) { classes[x.nome_en] = (classes[x.nome_en] || 0) + 1; });
        var nomes = Object.keys(classes);
        ctx.texto("pixel", nomes.length === 1 ? "Every year from " + px[0].ano + " to " + px[px.length - 1].ano + ", the pixel is <b>" + fmt.esc(nomes[0].toLowerCase()) + "</b>: a stable reading."
          : "Over " + px.length + " years the pixel takes " + nomes.length + " classes: " + nomes.map(function (k) { return fmt.esc(k.toLowerCase()) + " (" + classes[k] + ")"; }).join(", ") + ". A class that appears for a single year is more likely map error than change.");
      },

      idade: function (ctx, d) {
        var el = ctx.$("#fig-idade"), I = d.idade, rp = d.raio_principal;
        if (!I) return faltou(el, "NTEMS");
        ctx.tiles({ idade: camada(d, "idade", 0.8) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>NTEMS stand age, 2019</b><span><i class="g" style="background:linear-gradient(90deg,#d9f0a3,#41ab5d,#004529)"></i>young → old</span>');
        var c = I.classes[rp] || [], tot = c.reduce(function (s, x) { return s + x.ha; }, 0);
        graf.colunas(el, { x: c.map(function (x) { return x.faixa; }), valores: c.map(function (x) { return x.ha; }), unidade: "ha of forest by age (years), " + rot(rp) + " circle",
          cor: function (r) { var x = c.filter(function (y) { return y.faixa === r; })[0]; return x ? x.cor : "#41ab5d"; }, rotular: true });
        var jovem = c.filter(function (x) { return x.faixa === "0–20"; })[0], s = I.resumo[rp], ip = d.idade_ponto;
        ctx.texto("idade", "Forest covers <b>" + fmt.pct(florestaPct(d, rp)) + "</b> of the " + rot(rp) + " circle, and its median stand is " + fmt.esc(s.median_bin) + " years old. " +
          (jovem ? "<b>" + fmt.ha(jovem.ha) + "</b> (" + fmt.pct(100 * jovem.ha / tot) + ") is under 20 years: forest that burned or was cut since about 2000 and is growing back. " : "") +
          (ip && ip.is_forest ? "The stand at the point, at " + ip.age + " years, is among the older ones." : ""));
      },

      mudanca: function (ctx, d) {
        var el = ctx.$("#fig-mudanca"), M = d.mudanca;
        if (!M) return faltou(el, "Hansen/GLAD");
        ctx.tiles({ hansen: camada(d, "hansen", 0.9) });
        ctx.vetores(vet(d, d.raios));
        ctx.enquadrar(disco(d, "10"), { maxZoom: 13 });
        ctx.legendaMapa('<b>Hansen/GLAD</b><span><i style="background:#d4271e"></i>loss since 2001</span><span><i style="background:#02d659"></i>gain (undated)</span>');
        graf.tabela(el, {
          colunas: [{ rotulo: "Circle" }, { rotulo: "Forest 2000", n: true }, { rotulo: "Lost", n: true }, { rotulo: "Share lost", n: true }],
          linhas: d.raios.map(function (r) { var x = M.raios[r] || {};
            return [graf.qd(COR_RAIO[r]) + rot(r), fmt.ha(x.forest2000_ha), fmt.ha(x.loss_ha), fmt.pct(x.forest2000_ha ? 100 * x.loss_ha / x.forest2000_ha : 0)]; }),
          nota: "Canopy above " + M.limiar_pct + "% in 2000 counts as forest. Gain is a single flag over 2000–2012."
        });
        var a = M.raios["0.5"] || {}, b = M.raios["10"] || {};
        ctx.texto("mudanca", "Since 2001, the 10 km circle lost <b>" + fmt.ha(b.loss_ha) + "</b> of tree cover, " + fmt.pct(100 * b.loss_ha / b.forest2000_ha) +
          " of its forest in 2000, and gained " + fmt.ha(b.gain_ha) + ". Around the point, in the 0.5 km circle, " + fmt.pct(100 * a.loss_ha / a.forest2000_ha) + " was lost.");
      },

      perda: function (ctx, d) {
        var el = ctx.$("#fig-perda"), P = d.perda, rp = d.raio_principal;
        if (!P) return faltou(el, "Hansen/GLAD");
        ctx.tiles({ hansen: camada(d, "hansen", 0.9) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>Hansen/GLAD · loss since 2001</b><span><i style="background:#d4271e"></i>' + rot(rp) + " circle</span>");
        graf.colunas(el, { x: P.map(function (x) { return String(x.ano); }), valores: P.map(function (x) { return x.ha; }), unidade: "ha of tree cover lost per year, " + rot(rp) + " circle", cor: "#d4271e" });
        var top = P.slice().sort(function (a, b) { return b.ha - a.ha; }), tot = P.reduce(function (s, x) { return s + x.ha; }, 0);
        var dois = top.slice(0, 2).sort(function (a, b) { return a.ano - b.ano; });
        var seguidos = dois.length === 2 && dois[1].ano - dois[0].ano === 1;
        ctx.texto("perda", "<b>" + dois.map(function (x) { return x.ano; }).join(" and ") + "</b> together hold " + fmt.ha(dois[0].ha + (dois[1] ? dois[1].ha : 0)) + ", " +
          fmt.pct(100 * (dois[0].ha + (dois[1] ? dois[1].ha : 0)) / tot) + " of all the loss since 2001. " +
          (seguidos && dois[0].ano === 2003 && d.exemplo_padrao ? "August 2003 is the Okanagan Mountain Park fire, which burned the Myra Canyon trestles a few kilometres south of this point; the 2004 column is mostly the same fire, booked the year after." :
           seguidos ? "Two years in a row usually means one event, booked across both." : ""));
      },

      procedencia: function (ctx, d) {
        ctx.tiles({}); ctx.vetores({}); ctx.legendaMapa("");
        graf.tabela(ctx.$("#fig-procedencia"), {
          colunas: [{ rotulo: "Analysis" }, { rotulo: "Source (asset)" }, { rotulo: "Scale", n: true }, { rotulo: "Computed", n: true }],
          linhas: (d.procedencia || []).map(function (p) { return [fmt.esc(p.nome), '<code style="font-size:11px;overflow-wrap:anywhere">' + fmt.esc(p.dataset) + "</code>", p.escala_m ? p.escala_m + " m" : "—", fmt.data(p.calculado_em)]; }),
          nota: "This table travels with the spreadsheet."
        });
        ctx.texto("procedencia", "This point took " + (d.procedencia || []).length + " Earth Engine analyses, all from the run of " + fmt.dataHora(d.gerado_em) + ".");
      }
    }
  });
})();
