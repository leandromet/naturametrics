/* Naturametrics — the USA walkthrough (/walkthrough/usa, Paradise CA).
 *
 * The numbers come from /_demonstracao/naturametrics_us.json
 * (usa/services/demonstracao.py), built by the USA page's own services.
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
  function somaAno(h, r) {                       // total ha per year across all classes of a radius
    var z = h.raios[r] || {};
    return h.anos.map(function (_, i) { return Object.keys(z).reduce(function (s, c) { return s + (z[c][i] || 0); }, 0); });
  }
  function piorAno(h, r) {                       // the year with the most area, over a class-history package
    var t = somaAno(h, r), j = 0; t.forEach(function (v, i) { if (v > t[j]) j = i; });
    return { ano: h.anos[j], ha: t[j] };
  }
  function classeTop(h, r, ano) {                // class with the most area in one year
    var z = h.raios[r] || {}, i = h.anos.indexOf(ano), best = null;
    Object.keys(z).forEach(function (c) { var v = z[c][i] || 0; if (!best || v > best.ha) best = { id: c, ha: v, nome: h.classes[c].nome_en }; });
    return best;
  }
  function serieClasses(h, r) {
    var z = h.raios[r] || {};
    return Object.keys(z).map(function (c) { return { rotulo: h.classes[c].nome_en || h.classes[c].nome, cor: h.classes[c].cor, valores: z[c] }; })
      .filter(function (s) { return s.valores.some(function (v) { return v > 0.5; }); });
  }
  function jovemPct(d, r) {                      // forest area disturbed within 10 years, as a share of the forest area
    var c = (d.idade && d.idade.classes[r]) || [], tot = 0, jov = 0;
    c.forEach(function (x) { tot += x.ha; if (x.faixa === "0–5" || x.faixa === "6–10") jov += x.ha; });
    return tot > 0 ? 100 * jov / tot : null;
  }

  R.iniciar({
    dados: function (ctx) {
      var lat = parseFloat(ctx.params.get("lat")), lon = parseFloat(ctx.params.get("lon"));
      return "/_demonstracao/naturametrics_us.json" + (isFinite(lat) && isFinite(lon) ? "?lat=" + lat + "&lon=" + lon : "");
    },
    centro: [39.76, -121.62], zoom: 11,

    aoCarregar: function (ctx, d) {
      var rp = d.raio_principal, p = d.ponto, app = "/usa?lat=" + p.lat + "&lon=" + p.lon + "&lang=en";
      var pf = d.fogo ? piorAno(d.fogo, rp) : null, dos = d.dossel && d.dossel.raios[rp];
      var perdaTot = (d.perda || []).reduce(function (s, x) { return s + x.ha; }, 0), jp = jovemPct(d, rp);
      ctx.preencher({
        "n-fogo": pf && pf.ha > 0 ? fmt.ha(pf.ha) : "—",
        "n-fogo-rot": pf && pf.ha > 0 ? "burned in " + pf.ano + ", the worst fire year within " + rot(rp) + ' (MTBS) <span class="selo real">measured</span>' : "no MTBS-mapped fire within " + rot(rp),
        "n-dossel": dos ? fmt.n(dos[0], 0) + "% → " + fmt.n(dos[dos.length - 1], 0) + "%" : "—",
        "n-dossel-rot": "mean tree canopy within " + rot(rp) + ", " + (d.dossel ? d.dossel.anos[0] + " to " + d.dossel.anos[d.dossel.anos.length - 1] : "") + ' <span class="selo estimado">estimated</span>',
        "n-jovem": jp === null ? "—" : fmt.pct(jp),
        "n-jovem-rot": "of the forest within " + rot(rp) + ' disturbed in the last 10 years <span class="selo estimado">estimated</span>',
        "n-perda": perdaTot ? fmt.ha(perdaTot) : "—",
        "n-perda-rot": "of tree cover lost within " + rot(rp) + ' since 2001 (Hansen) <span class="selo real">measured</span>'
      });
      ctx.$("#link-app").href = app; ctx.$("#cta-app").href = app;
      ctx.$("#rp-fig-url").textContent = "naturametrics.umaterra.com.br" + app;
      ctx.$("#topo-exemplo").textContent = fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4);
      ctx.$("#abertura-exemplo").innerHTML = (d.exemplo_padrao ? "This page's example: Paradise, California, a town in the conifer forest of the Sierra foothills, burned almost entirely by the Camp Fire of November 2018, " : "Chosen point: ") +
        "<b>" + fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4) + "</b>, computed by the app's services on " + fmt.dataHora(d.gerado_em) +
        (d.exemplo_padrao ? " and stored with this page." : " (the result is kept for a few hours).");
      var erros = Object.keys(d.erros || {});
      ctx.$("#fim-extra").innerHTML = erros.length
        ? "These did not respond this time: <b>" + erros.map(fmt.esc).join(", ") + "</b>. The matching steps say what is missing."
        : "Every analysis responded in the run of " + fmt.dataHora(d.gerado_em) + ".";
      var h = d.historico;
      ctx.texto("ponto", "Here the point falls at " + fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4) + (d.regiao === "ak" ? ", in Alaska, where NLCD has three snapshot years instead of a series" : d.regiao === "hi" ? ", in Hawaii, where there is no NLCD land cover" : "") + ".");
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
        ctx.$("#fig-ponto").innerHTML = '<dl class="rp-ficha"><dt>Latitude</dt><dd>' + fmt.n(d.ponto.lat, 5) + "</dd><dt>Longitude</dt><dd>" + fmt.n(d.ponto.lon, 5) +
          "</dd><dt>Circles</dt><dd>" + d.raios.map(rot).join(" · ") + "</dd></dl>";
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
        if (!h) return faltou(el, "Annual NLCD");
        var ultimo = h.anos[h.anos.length - 1];
        ctx.tiles({ nlcd: camada(d, "nlcd_" + ultimo, 0.8) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa("<b>NLCD " + ultimo + "</b>" + classesNoAno(d, rp, h.anos.length - 1).slice(0, 6).map(function (c) { return '<span><i style="background:' + c.cor + '"></i>' + fmt.esc(c.nome) + "</span>"; }).join(""));
        graf.empilhado(el, { anos: h.anos, series: serieClasses(h, rp).sort(function (a, b) { return b.valores[b.valores.length - 1] - a.valores[a.valores.length - 1]; }), unidade: "ha" });
        var cf = classesNoAno(d, rp, h.anos.length - 1), c0 = classesNoAno(d, rp, 0);
        ctx.texto("historia", "In the " + rot(rp) + " circle, " + ultimo + ": " + cf.slice(0, 3).map(function (c) { return "<b>" + fmt.esc(c.nome.toLowerCase()) + "</b> " + fmt.ha(c.ha); }).join(", ") +
          ". In " + h.anos[0] + " the leading class was <b>" + fmt.esc(c0[0] ? c0[0].nome.toLowerCase() : "—") + "</b> (" + fmt.ha(c0[0] ? c0[0].ha : 0) + "). Classes that blink on and off between years are usually classification noise, not change on the ground.");
      },

      raios: function (ctx, d) {
        var el = ctx.$("#fig-raios"), h = d.historico;
        if (!h) return faltou(el, "Annual NLCD");
        ctx.tiles({ nlcd: camada(d, "nlcd_" + h.anos[0], 0.8) });
        ctx.vetores(vet(d, d.raios));
        ctx.enquadrar(disco(d, "10"), { maxZoom: 13 });
        ctx.legendaMapa("<b>NLCD " + h.anos[0] + "</b>" + d.raios.map(function (r) { return '<span><i style="background:' + COR_RAIO[r] + '"></i>' + rot(r) + "</span>"; }).join(""));
        var series = d.raios.map(function (r) { return { rotulo: rot(r), cor: COR_RAIO[r], valores: nativaPct(d, r), espessura: r === "0.5" ? 3 : 2 }; });
        graf.linhas(el, { x: h.anos, series: series, unidade: "% natural vegetation", min: 0, max: 100 });
        var n = h.anos.length - 1, p = series[0].valores[n], f = series[series.length - 1].valores[n];
        ctx.texto("raios", "In " + h.anos[n] + ", natural vegetation is <b>" + fmt.pct(p) + "</b> of the 0.5 km circle and <b>" + fmt.pct(f) + "</b> of the 10 km circle. " +
          (Math.abs(p - f) > 15 ? "The point and its surroundings are in different situations." : "Near and far look alike here."));
      },

      pixel: function (ctx, d) {
        var el = ctx.$("#fig-pixel"), px = d.pixel;
        if (!px || !px.length) return faltou(el, "The point's pixel");
        ctx.tiles({ nlcd: camada(d, "nlcd_" + px[px.length - 1].ano, 0.85) });
        ctx.vetores(vet(d));
        ctx.centro([d.ponto.lat, d.ponto.lon], 16);
        ctx.legendaMapa("<b>The 30 m pixel under the point</b>");
        el.innerHTML = '<div class="rp-caixa-tit">NLCD class of the point\'s pixel, year by year</div><div style="display:flex;flex-wrap:wrap;gap:3px">' +
          px.map(function (x) { return '<div title="' + fmt.esc(x.nome_en) + '" style="flex:1 0 44px;text-align:center;font:600 10.5px var(--rp-sans);padding:5px 2px;border-radius:3px;color:#fff;background:' + x.cor + '">' + x.ano + "</div>"; }).join("") + "</div>";
        var classes = {}; px.forEach(function (x) { classes[x.nome_en] = (classes[x.nome_en] || 0) + 1; });
        var nomes = Object.keys(classes);
        ctx.texto("pixel", nomes.length === 1 ? "Every year from " + px[0].ano + " to " + px[px.length - 1].ano + ", the pixel is <b>" + fmt.esc(nomes[0].toLowerCase()) + "</b>: a stable reading. A fire that took the trees would still not change a pixel that NLCD calls developed."
          : "Over " + px.length + " years the pixel takes " + nomes.length + " classes: " + nomes.map(function (k) { return fmt.esc(k.toLowerCase()) + " (" + classes[k] + ")"; }).join(", ") + ". A class that appears for a single year is more likely map error than change.");
      },

      disturbio: function (ctx, d) {
        var el = ctx.$("#fig-disturbio"), h = d.disturbio, rp = d.raio_principal;
        if (!h) return faltou(el, "LCMS disturbance history");
        ctx.tiles({ lcms: camada(d, "lcms", 0.85) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>LCMS · year of last disturbance</b><span><i class="g" style="background:linear-gradient(90deg,#ffffb2,#fd8d3c,#800026)"></i>1985 → 2025</span>');
        graf.empilhado(el, { anos: h.anos, series: serieClasses(h, rp), unidade: "ha changed per year, " + rot(rp) + " circle" });
        var pa = piorAno(h, rp), top = classeTop(h, rp, pa.ano);
        ctx.texto("disturbio", "The year with the most change in the " + rot(rp) + " circle is <b>" + pa.ano + "</b>: " + fmt.ha(pa.ha) + ", mostly <b>" + fmt.esc(top ? top.nome.toLowerCase() : "—") + "</b>. " +
          (top && /fire/i.test(top.nome) ? "A single event holds most of the record of the whole circle." : ""));
      },

      fogo: function (ctx, d) {
        var el = ctx.$("#fig-fogo"), h = d.fogo, rp = d.raio_principal;
        if (!h) { el.innerHTML = '<p class="rp-fig-estado">No fire mapped by MTBS within this circle: either none burned, or only fires smaller than MTBS maps (1,000 acres in the west, 500 in the east).</p>';
          ctx.tiles({}); ctx.vetores(vet(d, [rp])); ctx.enquadrar(disco(d, rp), { maxZoom: 13 }); ctx.legendaMapa(""); ctx.texto("fogo", "MTBS maps no fire here."); return; }
        ctx.tiles({ mtbs: camada(d, "mtbs", 0.85) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>MTBS · highest severity on record</b><span><i style="background:#7fffd4"></i>low</span><span><i style="background:#ffff00"></i>moderate</span><span><i style="background:#ff0000"></i>high</span>');
        graf.empilhado(el, { anos: h.anos, series: serieClasses(h, rp), unidade: "ha burned per year, " + rot(rp) + " circle" });
        var pa = piorAno(h, rp), z = h.raios[rp] || {}, i = h.anos.indexOf(pa.ano), alta = z["4"] ? z["4"][i] : 0;
        ctx.texto("fogo", "MTBS maps <b>" + fmt.ha(pa.ha) + "</b> burned in " + pa.ano + " within the " + rot(rp) + " circle, <b>" + fmt.ha(alta) + "</b> of it at high severity (" + fmt.pct(pa.ha ? 100 * alta / pa.ha : 0) + "). " +
          "LCMS booked the same event a year later, in the year its effect first shows in the imagery.");
      },

      idade: function (ctx, d) {
        var el = ctx.$("#fig-idade"), I = d.idade, rp = d.raio_principal;
        if (!I) return faltou(el, "LCMS");
        ctx.tiles({ lcms: camada(d, "lcms", 0.8) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>LCMS · year of last disturbance</b><span><i class="g" style="background:linear-gradient(90deg,#ffffb2,#fd8d3c,#800026)"></i>1985 → 2025</span>');
        var c = I.classes[rp] || [], tot = c.reduce(function (s, x) { return s + x.ha; }, 0);
        graf.colunas(el, { x: c.map(function (x) { return x.faixa; }), valores: c.map(function (x) { return x.ha; }), unidade: "ha of forest by years since last disturbance, " + rot(rp) + " circle",
          cor: function (r) { var x = c.filter(function (y) { return y.faixa === r; })[0]; return x ? x.cor : "#41ab5d"; }, rotular: true });
        var jp = jovemPct(d, rp), cens = c.filter(function (x) { return x.faixa.indexOf("≥") === 0; })[0];
        ctx.texto("idade", "Forest covers <b>" + fmt.ha(tot) + "</b> of the " + rot(rp) + " circle today (" + fmt.pct(100 * tot / areaDisco(rp)) + "). <b>" + fmt.pct(jp) + "</b> of it was disturbed in the last ten years, and <b>" +
          fmt.pct(cens && tot ? 100 * cens.ha / tot : 0) + "</b> not at all since 1985 (the last bar, which is censored, not an age).");
      },

      dossel: function (ctx, d) {
        var el = ctx.$("#fig-dossel"), T = d.dossel, rp = d.raio_principal;
        if (!T) return faltou(el, "Tree Canopy Cover");
        ctx.tiles({ tcc: camada(d, "tcc_2025", 0.8) });
        ctx.vetores(vet(d, d.raios));
        ctx.enquadrar(disco(d, "10"), { maxZoom: 13 });
        ctx.legendaMapa('<b>Tree canopy cover 2025</b><span><i class="g" style="background:linear-gradient(90deg,#ffffe5,#78c679,#004529)"></i>0 → 100%</span>');
        var series = d.raios.map(function (r) { return { rotulo: rot(r), cor: COR_RAIO[r], valores: T.raios[r], espessura: r === rp ? 3 : 2 }; });
        graf.linhas(el, { x: T.anos, series: series, unidade: "% mean tree canopy", min: 0, max: 100 });
        var v = T.raios[rp], n = v.length - 1, minI = 0; v.forEach(function (x, i) { if (x < v[minI]) minI = i; });
        ctx.texto("dossel", "Within " + rot(rp) + ", mean canopy goes from <b>" + fmt.n(v[0], 0) + "%</b> in " + T.anos[0] + " to <b>" + fmt.n(v[n], 0) + "%</b> in " + T.anos[n] +
          ", with its low at <b>" + fmt.n(v[minI], 0) + "%</b> in " + T.anos[minI] + ". A canopy that falls in one year and climbs slowly after is a disturbance and a regrowth, not a decline.");
      },

      perda: function (ctx, d) {
        var el = ctx.$("#fig-perda"), P = d.perda, rp = d.raio_principal;
        if (!P) return faltou(el, "Hansen/GLAD");
        ctx.tiles({ hansen: camada(d, "hansen", 0.9) });
        ctx.vetores(vet(d, [rp]));
        ctx.enquadrar(disco(d, rp), { maxZoom: 13 });
        ctx.legendaMapa('<b>Hansen/GLAD</b><span><i style="background:#d4271e"></i>loss since 2001</span><span><i style="background:#02d659"></i>gain (undated)</span>');
        graf.colunas(el, { x: P.map(function (x) { return String(x.ano); }), valores: P.map(function (x) { return x.ha; }), unidade: "ha of tree cover lost per year, " + rot(rp) + " circle", cor: "#d4271e" });
        var top = P.slice().sort(function (a, b) { return b.ha - a.ha; }), tot = P.reduce(function (s, x) { return s + x.ha; }, 0);
        ctx.texto("perda", "Hansen puts the largest loss in <b>" + top[0].ano + "</b>: " + fmt.ha(top[0].ha) + ", " + fmt.pct(tot ? 100 * top[0].ha / tot : 0) + " of all the loss since 2001 in this circle. Compare with the LCMS and MTBS years above: the three products book the same event in neighbouring years.");
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
