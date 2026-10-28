/* Naturametrics — demonstração em rolagem (/demonstracao, e /walkthrough em inglês).
 *
 * Os números vêm de /_demonstracao/naturametrics.json (services/demonstracao.py),
 * montado pelos mesmos serviços que a interface usa ao clicar num ponto. Este
 * arquivo só decide o que cada passo mostra; nenhum valor é escrito à mão. Os
 * textos vêm nas duas línguas, t("pt", "en"), e a página escolhe pela sua.
 */
(function () {
  var R = window.Reportagem, fmt = R.fmt, graf = R.graf;
  var t, en;   // definidos em aoCarregar (dependem da língua da página)

  var COR_RAIO = { "0.5": "#d98324", "1": "#b5651d", "2": "#1f6f4a", "5": "#4f8f6f", "10": "#9cc2ac" };
  var COR_PERDA = "#e5484d", COR_GANHO = "#30a46c";
  // os grupos de services/ibge_vegetation.bucket_matrix (aqui sem rótulos no pacote)
  var GRUPO_IBGE = {
    natural_forest: ["Natural — floresta", "Natural — forest"], natural_non_forest: ["Natural — não florestal", "Natural — non-forest"],
    anthropic_forest: ["Antrópico — floresta plantada", "Human — planted forest"], anthropic_regrowth: ["Antrópico — vegetação secundária", "Human — secondary growth"],
    anthropic_non_forest: ["Antrópico — agropecuária/urbano", "Human — farming/urban"], water: ["Água", "Water"], other: ["Outros/sem dados", "Other/no data"]
  };

  function rot(r) { return fmt.n(Number(r), Number(r) < 1 ? 1 : 0) + " km"; }
  function k(r) { return String(r).replace(/\.0$/, ""); }
  function principal(d) { return k(d.raio_principal); }
  function nomeClasse(c) { return en ? (c.nome_en || c.nome) : c.nome; }
  // "6–10 anos" e "≥ 39 (natural desde 1987)" vêm do serviço em português
  function faixaIdade(s) {
    if (!en) return s;
    return s.replace(/ anos?/, " years").replace(/\(natural desde (\d+)\)/, "(natural since $1)");
  }
  function discos(d, so) {
    return { type: "FeatureCollection", features: d.buffers.features.filter(function (f) {
      return f.properties.role === "buffer" && (!so || so.indexOf(k(f.properties.radius_km)) >= 0);
    }) };
  }
  function pontoGeo(d) { return { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [d.ponto.lon, d.ponto.lat] } }; }
  function vetBase(d, extra) {
    var v = {
      discos: { geojson: discos(d), estilo: function (f) { return { color: COR_RAIO[k(f.properties.radius_km)] || "#fff", weight: 1.5, dashArray: "5 4", fillOpacity: 0 }; } },
      ponto: { geojson: pontoGeo(d), ponto: { radius: 6, color: "#fff", weight: 2, fillColor: "#d98324", fillOpacity: 1 } }
    };
    return Object.assign(v, extra || {});
  }
  function nativaPct(d, raio) {
    var h = d.historico, z = h.raios[raio] || {}, nat = h.nativas.map(String);
    return h.anos.map(function (_, i) {
      var tot = 0, n = 0;
      Object.keys(z).forEach(function (c) { tot += z[c][i] || 0; if (nat.indexOf(c) >= 0) n += z[c][i] || 0; });
      return tot > 0 ? (100 * n) / tot : null;
    });
  }
  function classesNoAno(d, raio, i) {
    var h = d.historico, z = h.raios[raio] || {};
    return Object.keys(z).map(function (c) { return { id: c, ha: z[c][i] || 0, nome: nomeClasse(h.classes[c]), cor: h.classes[c].cor }; })
      .filter(function (x) { return x.ha > 0; }).sort(function (a, b) { return b.ha - a.ha; });
  }
  function legendaClasses(d, i, raio) {
    return "<b>MapBiomas " + d.historico.anos[i] + " · " + t("no círculo de ", "in the ") + rot(raio) + t("", " disc") + "</b>" + classesNoAno(d, raio, i).slice(0, 6).map(function (c) {
      return '<span><i style="background:' + c.cor + '"></i>' + fmt.esc(c.nome) + "</span>";
    }).join("");
  }
  function camada(d, chave, op) { var c = d.camadas[chave]; return c ? Object.assign({}, c, op ? { opacity: op } : {}) : null; }
  function faltou(el, nome) {
    el.innerHTML = '<p class="rp-fig-estado erro">' + nome + t(" não respondeu desta vez ", " did not respond this time ") +
      '<span class="selo ausente">' + t("ausente", "missing") + "</span></p>";
  }
  function nomeLugar(d) {
    var p = d.ponto;
    return p.conglomerado ? p.conglomerado + (p.municipio ? " · " + p.municipio + "/" + p.uf : "") : fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4);
  }
  function linkApp(d) {
    var p = d.ponto;
    return (p.conglomerado ? "/?ifn=" + encodeURIComponent(p.conglomerado) : "/?lat=" + p.lat + "&lon=" + p.lon) + (en ? "&lang=en" : "");
  }
  var selo = function () { return ' <span class="selo real">' + t("real", "measured") + "</span>"; };

  R.iniciar({
    dados: function (ctx) {
      var q = [], ifn = ctx.params.get("ifn"), lat = ctx.params.get("lat"), lon = ctx.params.get("lon");
      if (ifn) q.push("ifn=" + encodeURIComponent(ifn));
      else if (lat && lon) q.push("lat=" + encodeURIComponent(lat), "lon=" + encodeURIComponent(lon));
      return "/_demonstracao/naturametrics.json" + (q.length ? "?" + q.join("&") : "");
    },
    centro: [-12, -55], zoom: 5,

    aoCarregar: function (ctx, d) {
      t = ctx.t; en = ctx.lang === "en";
      var p = d.ponto, rp = principal(d), h = d.historico;
      var nat = h ? nativaPct(d, rp) : [];
      var mud = d.mudanca && d.mudanca.raios[rp];
      var nIbama = ((d.embargos || {}).features || []).length + ((d.autos || {}).features || []).length;
      ctx.preencher({
        "n-nativa0": h ? fmt.pct(nat[0]) : "—",
        "n-nativa0-rot": h ? t("de vegetação nativa no círculo de " + rot(rp) + " em ", "native vegetation in the " + rot(rp) + " disc in ") + h.anos[0] + selo() : t("de vegetação nativa no primeiro ano", "native vegetation in the first year"),
        "n-nativa1": h ? fmt.pct(nat[nat.length - 1]) : "—",
        "n-nativa1-rot": h ? t("no mesmo círculo em ", "in the same disc in ") + h.anos[h.anos.length - 1] + selo() : t("de vegetação nativa no último ano", "native vegetation in the latest year"),
        "n-perda": mud ? fmt.ha(mud.loss_ha) : "—",
        "n-perda-rot": t("de vegetação nativa perdida no círculo desde ", "of native vegetation lost in the disc since ") + (d.mudanca ? d.mudanca.de : 2008) + selo(),
        "n-ibama": fmt.n(nIbama)
      });
      ctx.$("#topo-exemplo").textContent = nomeLugar(d);
      ctx.$("#link-app").href = linkApp(d); ctx.$("#cta-app").href = linkApp(d);
      ctx.$("#rp-fig-url").textContent = "naturametrics.umaterra.com.br" + linkApp(d);
      ctx.$("#abertura-exemplo").innerHTML = (d.exemplo_padrao ? t("Exemplo desta página: ", "This page's example: ") : t("Ponto escolhido: ", "Chosen point: ")) + "<b>" + fmt.esc(nomeLugar(d)) + "</b>" +
        (p.bioma ? t(", bioma ", ", ") + fmt.esc(p.bioma) + t("", " biome") : "") + t(". Calculado pelos serviços do aplicativo em ", ". Computed by the app's services on ") + fmt.dataHora(d.gerado_em) +
        (d.exemplo_padrao ? t(" e guardado com esta página.", " and stored with this page.") : t(" (o resultado fica guardado por algumas horas).", " (the result is kept for a few hours)."));
      var erros = Object.keys(d.erros || {});
      ctx.$("#fim-extra").innerHTML = erros.length
        ? t("Desta vez não responderam: ", "These did not respond this time: ") + "<b>" + erros.map(fmt.esc).join(", ") + "</b>. " + t("Os passos correspondentes dizem o que faltou.", "The matching steps say what is missing.")
        : t("Todas as análises responderam no cálculo de ", "Every analysis responded in the run of ") + fmt.dataHora(d.gerado_em) + ".";
      var coord = fmt.n(Math.abs(p.lat), 4) + "°" + (p.lat < 0 ? "S" : "N") + " " + fmt.n(Math.abs(p.lon), 4) + "°" + (p.lon < 0 ? t("O", "W") : t("L", "E"));
      ctx.texto("ponto", p.conglomerado
        ? t("Aqui o ponto é o conglomerado <b>" + fmt.esc(p.conglomerado) + "</b>, em " + fmt.esc(p.municipio || "—") + "/" + fmt.esc(p.uf || "—") + ", na coordenada <b>" + coord + "</b>.",
            "Here the point is plot <b>" + fmt.esc(p.conglomerado) + "</b>, in " + fmt.esc(p.municipio || "—") + "/" + fmt.esc(p.uf || "—") + ", at <b>" + coord + "</b>.")
        : t("Aqui o ponto é a coordenada pedida no endereço, <b>" + coord + "</b>.", "Here the point is the coordinate given in the address, <b>" + coord + "</b>."));
      var vizinhos = ((d.ifn || {}).features || []).length;
      ctx.texto("ifn", vizinhos > 1
        ? t("No quadrado de 20 km em volta deste ponto há <b>" + vizinhos + " conglomerados</b>, em branco no mapa.", "The 20 km square around this point holds <b>" + vizinhos + " plots</b>, white on the map.")
        : t("A grade do IFN é larga: no quadrado de 20 km em volta deste ponto, " + (vizinhos === 1 ? "este é o único conglomerado." : "não há nenhum conglomerado."),
            "The inventory grid is wide: in the 20 km square around this point, " + (vizinhos === 1 ? "this is the only plot." : "there is no plot.")));
      var areas = d.raios.map(function (r) { return "<b>" + fmt.ha(d.areas_ha[k(r)]) + "</b>"; }).join(", ");
      ctx.texto("discos", t("Do menor ao maior: " + areas + ". O círculo de 10 km tem 400 vezes a área do de 0,5 km — o raio muda a escala da pergunta.",
        "From smallest to largest: " + areas + ". The 10 km disc is 400 times the 0.5 km one — the radius changes the scale of the question."));
    },

    passos: {
      ponto: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores({ ponto: vetBase(d).ponto });
        ctx.enquadrar(discos(d, ["1"]), { maxZoom: 14 });
        ctx.legendaMapa("");
        var p = d.ponto;
        ctx.$("#fig-ponto").innerHTML = '<dl class="rp-ficha"><dt>' + t("Origem", "Source") + "</dt><dd>" + (p.conglomerado ? t("conglomerado do IFN", "inventory plot") : t("coordenada", "coordinate")) + "</dd>" +
          (p.conglomerado ? "<dt>" + t("Conglomerado", "Plot") + "</dt><dd>" + fmt.esc(p.conglomerado) + "</dd><dt>" + t("Município", "Municipality") + "</dt><dd>" + fmt.esc(p.municipio) + "/" + fmt.esc(p.uf) +
            "</dd><dt>" + t("Bioma", "Biome") + "</dt><dd>" + fmt.esc(p.bioma) + "</dd>" : "") +
          "<dt>" + t("Coordenada", "Coordinate") + "</dt><dd>" + fmt.n(p.lat, 5) + ", " + fmt.n(p.lon, 5) + "</dd></dl>";
      },

      ifn: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores({
          ifn: { geojson: d.ifn, ponto: function (f) { var eu = f.properties.conglomerado === d.ponto.conglomerado; return { radius: eu ? 8 : 5, color: "#fff", weight: 2, fillColor: eu ? "#d98324" : "#ffffff", fillOpacity: eu ? 1 : 0.85 }; },
            popup: function (f) { return fmt.esc(f.properties.conglomerado) + " · " + fmt.esc(f.properties.municipio || "") + " · " + fmt.esc(f.properties.bioma || ""); } }
        });
        ctx.enquadrar([[d.bbox[1], d.bbox[0]], [d.bbox[3], d.bbox[2]]], { maxZoom: 12 });
        ctx.legendaMapa('<span><i style="background:#d98324"></i>' + t("este conglomerado", "this plot") + '</span><span><i style="background:#fff;border:1px solid #9aa8a1"></i>' + t("outros conglomerados", "other plots") + "</span>");
        var fs = ((d.ifn || {}).features || []);
        graf.tabela(ctx.$("#fig-ifn"), {
          colunas: [{ rotulo: t("Conglomerado", "Plot") }, { rotulo: t("Município", "Municipality") }, { rotulo: t("Bioma", "Biome") }],
          linhas: fs.slice(0, 6).map(function (f) { var q = f.properties, eu = q.conglomerado === d.ponto.conglomerado; return [(eu ? "<b>" : "") + fmt.esc(q.conglomerado) + (eu ? "</b>" : ""), fmt.esc(q.municipio || "—") + "/" + fmt.esc(q.uf || ""), fmt.esc(q.bioma || "")]; }),
          nota: t("17.479 pontos no catálogo do aplicativo, com as coordenadas publicadas pelo Serviço Florestal Brasileiro.", "17,479 points in the app's catalogue, at the coordinates published by the Brazilian Forest Service.")
        });
      },

      discos: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa(d.raios.map(function (r) { return '<span><i style="background:' + COR_RAIO[k(r)] + '"></i>' + rot(r) + "</span>"; }).join(""));
        graf.tabela(ctx.$("#fig-discos"), {
          colunas: [{ rotulo: t("Raio", "Radius") }, { rotulo: t("Área do círculo", "Disc area"), n: true }, { rotulo: t("× o de 0,5 km", "× the 0.5 km disc"), n: true }],
          linhas: d.raios.map(function (r) { return [graf.qd(COR_RAIO[k(r)]) + rot(r), fmt.ha(d.areas_ha[k(r)]), fmt.n(d.areas_ha[k(r)] / d.areas_ha["0.5"], 0)]; })
        });
      },

      historia: function (ctx, d) {
        var el = ctx.$("#fig-historia"), h = d.historico, rp = principal(d);
        if (!h) return faltou(el, "O MapBiomas");
        var ultimo = h.anos.length - 1;
        ctx.tiles({ mb: camada(d, "mb_" + h.anos[ultimo], 0.85) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, [rp]), { maxZoom: 13 });
        ctx.legendaMapa(legendaClasses(d, ultimo, rp));
        var z = h.raios[rp];
        var series = Object.keys(z).map(function (c) { return { rotulo: nomeClasse(h.classes[c]), cor: h.classes[c].cor, valores: z[c] }; })
          .sort(function (a, b) { return b.valores[ultimo] - a.valores[ultimo]; });
        graf.empilhado(el, { anos: h.anos, series: series, unidade: t("ha no círculo de ", "ha in the ") + rot(rp) + t("", " disc"), dec: 0, marcas: [{ ano: 2008, rotulo: "2008" }] });
        var c0 = classesNoAno(d, rp, 0)[0], cf = classesNoAno(d, rp, ultimo)[0], troca = null;
        for (var i = 1; i <= ultimo; i++) { var ci = classesNoAno(d, rp, i)[0]; if (ci && c0 && ci.id !== c0.id) { troca = { ano: h.anos[i], c: ci }; break; } }
        var b = function (x) { return "<b>" + fmt.esc(x.nome.toLowerCase()) + "</b>"; };
        ctx.texto("historia", t(
          "No círculo de " + rot(rp) + ", o que mais havia em " + h.anos[0] + " era " + b(c0) + " (" + fmt.ha(c0.ha) + "). " +
          (troca ? "Em <b>" + troca.ano + "</b>, " + b(troca.c) + " passa à frente. " : "Ela segue na frente até o fim da série. ") +
          "Em " + h.anos[ultimo] + ", " + b(cf) + " ocupa " + fmt.ha(cf.ha) + ".",
          "In the " + rot(rp) + " disc, the largest class in " + h.anos[0] + " was " + b(c0) + " (" + fmt.ha(c0.ha) + "). " +
          (troca ? "In <b>" + troca.ano + "</b>, " + b(troca.c) + " takes over. " : "It stays in front to the end of the series. ") +
          "In " + h.anos[ultimo] + ", " + b(cf) + " covers " + fmt.ha(cf.ha) + "."));
      },

      raios: function (ctx, d) {
        var el = ctx.$("#fig-raios"), h = d.historico;
        if (!h) return faltou(el, "O MapBiomas");
        ctx.tiles({ mb: camada(d, "mb_" + h.anos[0], 0.85) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa(legendaClasses(d, 0, "10"));
        var series = d.raios.map(function (r) { return { rotulo: rot(r), cor: COR_RAIO[k(r)], valores: nativaPct(d, k(r)), espessura: k(r) === "0.5" ? 3 : 2 }; });
        graf.linhas(el, { x: h.anos, series: series, unidade: t("% de vegetação nativa no círculo", "% native vegetation in the disc"), min: 0, max: 100, marcas: [{ x: 2008, rotulo: "2008" }] });
        // em que ano cada círculo passou a ter menos da metade de vegetação nativa
        var meio = series.map(function (s) { for (var i = 0; i < s.valores.length; i++) if (s.valores[i] !== null && s.valores[i] < 50) return { r: s.rotulo, ano: h.anos[i] }; return { r: s.rotulo, ano: null }; });
        var lista = meio.map(function (m) { return m.r + " → <b>" + (m.ano || t("nunca", "never")) + "</b>"; }).join(", ");
        ctx.texto("raios", meio.some(function (m) { return m.ano; })
          ? t("Ano em que cada círculo ficou com menos da metade de vegetação nativa: " + lista + ".", "Year in which each disc dropped below half native vegetation: " + lista + ".")
          : t("Nenhum círculo chegou a ter menos da metade de vegetação nativa na série.", "No disc dropped below half native vegetation in the series."));
      },

      pixel: function (ctx, d) {
        var el = ctx.$("#fig-pixel"), px = d.pixel, h = d.historico;
        if (!px) return faltou(el, t("A série do pixel", "The pixel series"));
        ctx.tiles({ mb: camada(d, "mb_" + px[px.length - 1].ano, 0.85) });
        ctx.vetores(vetBase(d));
        ctx.centro([d.ponto.lat, d.ponto.lon], 16);
        ctx.legendaMapa("<b>" + t("O ponto sobre o pixel de 30 m do último ano", "The point over the latest year's 30 m pixel") + "</b>");
        var nomePx = function (x) { return en ? (x.nome_en || x.nome) : x.nome; };
        // uma faixa de anos, uma célula por ano, na cor da classe do pixel
        // (margem de 24 nos dois lados para o primeiro e o último ano não saírem do desenho)
        var n = px.length, w = 712 / n, x0 = 24, s = "", trocas = [];
        px.forEach(function (x, i) {
          var cor = (h && h.classes[String(x.classe)] || {}).cor || "#9aa8a1";
          s += '<rect x="' + (x0 + i * w) + '" y="20" width="' + (w - 1) + '" height="46" fill="' + cor + '"><title>' + x.ano + ": " + fmt.esc(nomePx(x)) + "</title></rect>";
          if (i % 5 === 0 || i === n - 1) s += '<text class="eixo" x="' + (x0 + i * w + w / 2) + '" y="84" text-anchor="middle">' + x.ano + "</text>";
          if (i > 0 && x.classe !== px[i - 1].classe) trocas.push(x);
        });
        var vistas = {}; px.forEach(function (x) { vistas[nomePx(x)] = (h && h.classes[String(x.classe)] || {}).cor || "#9aa8a1"; });
        el.innerHTML = '<svg class="rp-sv" viewBox="0 0 760 92" role="img" aria-label="' + t("Classe do pixel por ano", "Pixel class by year") + '">' + s + "</svg>" +
          graf.legenda(Object.keys(vistas).map(function (nm) { return { rotulo: nm, cor: vistas[nm] }; }));
        var lista = trocas.slice(0, 4).map(function (x) { return x.ano + " (" + fmt.esc(nomePx(x).toLowerCase()) + ")"; }).join(", ") + (trocas.length > 4 ? "…" : "");
        ctx.texto("pixel", trocas.length
          ? t("Neste pixel, o classificador trocou de classe <b>" + trocas.length + (trocas.length > 1 ? " vezes" : " vez") + "</b>: " + lista + ".",
              "In this pixel the classifier changed class <b>" + trocas.length + (trocas.length > 1 ? " times" : " time") + "</b>: " + lista + ".")
          : t("Neste pixel, o classificador viu a mesma classe nos " + n + " anos: <b>" + fmt.esc(nomePx(px[0]).toLowerCase()) + "</b>.",
              "In this pixel the classifier saw the same class in all " + n + " years: <b>" + fmt.esc(nomePx(px[0]).toLowerCase()) + "</b>."));
      },

      mudanca: function (ctx, d) {
        var el = ctx.$("#fig-mudanca"), M = d.mudanca;
        if (!M) return faltou(el, t("A máscara de mudança", "The change mask"));
        ctx.tiles({ mud: camada(d, "mudanca", 0.9) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa("<b>" + t("Mudança ", "Change ") + M.de + " → " + M.ate + "</b>" + '<span><i style="background:' + COR_PERDA + '"></i>' + t("vegetação nativa perdida", "native vegetation lost") + '</span><span><i style="background:' + COR_GANHO + '"></i>' + t("regeneração", "regrowth") + "</span>");
        var linhas = [];
        d.raios.forEach(function (r) {
          var x = M.raios[k(r)]; if (!x) return;
          linhas.push({ rotulo: rot(r) + t(" · perda", " · loss"), valor: x.loss_ha, cor: COR_PERDA, texto: fmt.ha(x.loss_ha) });
          linhas.push({ rotulo: rot(r) + t(" · regeneração", " · regrowth"), valor: x.gain_ha, cor: COR_GANHO, texto: fmt.ha(x.gain_ha) });
        });
        graf.barrasH(el, { linhas: linhas, xRotulo: 190 });
        var x = M.raios[principal(d)], rp = rot(principal(d));
        if (x) ctx.texto("mudanca", t(
          "No círculo de " + rp + ", <b>" + fmt.ha(x.loss_ha) + "</b> que eram vegetação nativa em " + M.de + " deixaram de ser até " + M.ate +
          ", e <b>" + fmt.ha(x.gain_ha) + "</b> voltaram. Seguiram nativos nos dois anos " + fmt.ha(x.stable_ha) + ".",
          "In the " + rp + " disc, <b>" + fmt.ha(x.loss_ha) + "</b> that were native vegetation in " + M.de + " were no longer by " + M.ate +
          ", and <b>" + fmt.ha(x.gain_ha) + "</b> came back. " + fmt.ha(x.stable_ha) + " stayed native in both years."));
        ctx.legendaFig(t("A camada serve de triagem: aponta onde olhar, não constata ilegalidade. O Código Florestal decide pela data, pelo imóvel e pelas autorizações, que o satélite não vê.",
          "The layer is a screening tool: it points where to look, it does not establish illegality. The Forest Code turns on dates, properties and permits the satellite cannot see."));
      },

      idade: function (ctx, d) {
        var el = ctx.$("#fig-idade"), I = d.idade, rp = principal(d);
        if (!I) return faltou(el, t("A idade da vegetação", "Vegetation age"));
        ctx.tiles({ mb: camada(d, "mb_" + d.historico.anos[d.historico.anos.length - 1], 0.6) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, [rp]), { maxZoom: 13 });
        ctx.legendaMapa("");
        var fx = I.faixas[rp] || [], res = I.resumo[rp] || {};
        graf.barrasH(el, { linhas: fx.map(function (f) { return { rotulo: faixaIdade(f.faixa), valor: f.ha, cor: f.cor, texto: fmt.ha(f.ha) }; }), xRotulo: 230 });
        var serie = d.idade_ponto || [];
        if (serie.length) {
          var box = document.createElement("div"); el.appendChild(box);
          graf.linhas(box, { x: serie.map(function (x) { return x.ano; }), series: [{ rotulo: t("idade no pixel do ponto (anos)", "age at the point's pixel (years)"), cor: "#1f6f4a", valores: serie.map(function (x) { return x.idade; }), pontos: true }], min: 0, altura: 170, unidade: t("anos", "years") });
        }
        ctx.texto("idade", t(
          "No círculo de " + rot(rp) + " há <b>" + fmt.ha(res.total_natural_area_ha) + "</b> de vegetação hoje. Desse total, <b>" + fmt.pct(res.censored_pct, 1) +
          "</b> não tem idade conhecida: <i>" + fmt.esc(res.censored_label || "") + "</i>; a parte com data, " + fmt.ha(res.dated_area_ha) + ", tem mediana de <b>" + fmt.n(res.median_dated_age) + " anos</b>.",
          "The " + rot(rp) + " disc holds <b>" + fmt.ha(res.total_natural_area_ha) + "</b> of vegetation today. Of that, <b>" + fmt.pct(res.censored_pct, 1) +
          "</b> has no known age: <i>" + fmt.esc(faixaIdade(res.censored_label || "")) + "</i>; the dated part, " + fmt.ha(res.dated_area_ha) + ", has a median age of <b>" + fmt.n(res.median_dated_age) + " years</b>."));
      },

      metricas: function (ctx, d) {
        var el = ctx.$("#fig-metricas"), M = d.metricas;
        ctx.tiles({}); ctx.vetores({}); ctx.legendaMapa("");
        if (!M) return faltou(el, t("As métricas de paisagem", "The landscape metrics"));
        graf.tabela(el, {
          colunas: [{ rotulo: t("Raio", "Radius") }, { rotulo: t("Fragmentos", "Fragments"), n: true }, { rotulo: t("Por 100 ha", "Per 100 ha"), n: true }, { rotulo: t("Maior fragmento", "Largest fragment"), n: true },
            { rotulo: t("Malha efetiva", "Effective mesh"), n: true }, { rotulo: t("Borda (m/ha)", "Edge (m/ha)"), n: true }, { rotulo: "Shannon", n: true }],
          linhas: M.map(function (m) { return [rot(m.radius_km), fmt.n(m.patches), fmt.n(100 * m.patches / m.area_ha, 1), fmt.pct(m.largest_patch_pct, 1), fmt.ha(m.meff_ha), fmt.n(m.edge_density, 1), fmt.n(m.shannon, 2)]; }),
          nota: t("Fragmentos: manchas contínuas de uma mesma classe (vizinhança de 8 pixels) dentro de cada círculo, MapBiomas ", "Fragments: continuous patches of one class (8-pixel neighbourhood) inside each disc, MapBiomas ") +
            d.historico.anos[d.historico.anos.length - 1] + t(". Malha efetiva: o tamanho que um fragmento único precisaria ter para que dois pontos sorteados caíssem juntos com a mesma chance de hoje.",
            ". Effective mesh: the size a single fragment would need for two random points to land in the same patch as often as they do today.")
        });
        var a = M[0], b = M[M.length - 1];
        ctx.texto("metricas", t(
          "Do círculo de " + rot(a.radius_km) + " ao de " + rot(b.radius_km) + ", a densidade de fragmentos vai de <b>" + fmt.n(100 * a.patches / a.area_ha, 1) + "</b> a <b>" + fmt.n(100 * b.patches / b.area_ha, 1) +
          "</b> por 100 ha. No círculo de " + rot(b.radius_km) + ", o maior fragmento ocupa <b>" + fmt.pct(b.largest_patch_pct, 1) + "</b> da área, e a malha efetiva é de " + fmt.ha(b.meff_ha) +
          ". O número diz o quanto a paisagem é contínua, e não do quê: aqui, o maior fragmento é o próprio pasto.",
          "From the " + rot(a.radius_km) + " disc to the " + rot(b.radius_km) + " one, fragment density goes from <b>" + fmt.n(100 * a.patches / a.area_ha, 1) + "</b> to <b>" + fmt.n(100 * b.patches / b.area_ha, 1) +
          "</b> per 100 ha. In the " + rot(b.radius_km) + " disc the largest fragment covers <b>" + fmt.pct(b.largest_patch_pct, 1) + "</b> of the area, and the effective mesh is " + fmt.ha(b.meff_ha) +
          ". The number says how continuous the landscape is, not of what: here the largest fragment is the pasture itself."));
      },

      biomassa: function (ctx, d) {
        var el = ctx.$("#fig-biomassa"), B = d.biomassa, rp = principal(d);
        if (!B) return faltou(el, "O ESA CCI");
        ctx.tiles({ bio: camada(d, "biomassa", 0.75) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa("<b>ESA CCI · " + t("biomassa acima do solo", "above-ground biomass") + '</b><span><i class="g" style="background:linear-gradient(90deg,#fff,#008000)"></i>' + t("baixa → alta", "low → high") + "</span>");
        var serie = B[rp] || [], anos = serie.map(function (x) { return x.ano; });
        graf.linhas(el, {
          x: anos, unidade: "Mg/ha", min: 0,
          faixa: { min: serie.map(function (x) { return Math.max(0, x.mgha - x.sd); }), max: serie.map(function (x) { return x.mgha + x.sd; }), cor: "#4f8f6f" },
          series: d.raios.filter(function (r) { return B[k(r)] && (k(r) === rp || k(r) === "0.5" || k(r) === "10"); }).map(function (r) {
            var m = {}; B[k(r)].forEach(function (x) { m[x.ano] = x.mgha; });
            return { rotulo: rot(r) + (k(r) === rp ? t(" (faixa: ± 1 desvio-padrão)", " (band: ± 1 standard deviation)") : ""), cor: COR_RAIO[k(r)], valores: anos.map(function (a) { return m[a]; }), pontos: true, espessura: k(r) === rp ? 3 : 2 };
          })
        });
        if (serie.length) {
          var dp = fmt.n(serie.reduce(function (a, x) { return a + x.sd; }, 0) / serie.length);
          ctx.texto("biomassa", t(
            "No círculo de " + rot(rp) + ", a média vai de <b>" + fmt.n(serie[0].mgha) + " Mg/ha</b> em " + serie[0].ano + " a <b>" + fmt.n(serie[serie.length - 1].mgha) +
            " Mg/ha</b> em " + serie[serie.length - 1].ano + ". O desvio-padrão médio do produto no círculo é de ±" + dp + " Mg/ha.",
            "In the " + rot(rp) + " disc, the mean goes from <b>" + fmt.n(serie[0].mgha) + " Mg/ha</b> in " + serie[0].ano + " to <b>" + fmt.n(serie[serie.length - 1].mgha) +
            " Mg/ha</b> in " + serie[serie.length - 1].ano + ". The product's mean standard deviation in the disc is ±" + dp + " Mg/ha."));
        }
      },

      ibge: function (ctx, d) {
        var el = ctx.$("#fig-ibge"), I = d.ibge, rp = principal(d);
        ctx.tiles({ ibge: camada(d, "ibge", 0.75) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa("<b>" + t("IBGE · vegetação, rasterizada", "IBGE · vegetation, rasterised") + "</b>" + t("com a paleta do aplicativo", "in the app's palette"));
        if (!I) return faltou(el, t("O mapa do IBGE", "IBGE's map"));
        var nome = function (g) { return (GRUPO_IBGE[g] || [g, g])[en ? 1 : 0]; };
        var curto = function (g) { return nome(g).replace(/^(Antrópico|Natural|Human) — /, ""); };
        var g = I.groups.filter(function (a) { return I.groups.some(function (b) { return (I.matrix[a] || {})[b] > 0.05 || (I.matrix[b] || {})[a] > 0.05; }); });
        graf.tabela(el, {
          colunas: [{ rotulo: "IBGE ↓ · MapBiomas →" }].concat(g.map(function (a) { return { rotulo: curto(a), n: true }; })),
          linhas: g.map(function (a) { return [fmt.esc(nome(a))].concat(g.map(function (b) { var v = (I.matrix[a] || {})[b] || 0; return v > 0.05 ? (a === b ? "<b>" + fmt.pct(v, 1) + "</b>" : fmt.pct(v, 1)) : "·"; })); }),
          nota: t("Parte do círculo de " + rot(rp) + " em cada par de classes. Na diagonal, em negrito, os dois mapas concordam.", "Share of the " + rot(rp) + " disc in each pair of classes. On the diagonal, in bold, the two maps agree.")
        });
        ctx.texto("ibge", t(
          "No círculo de " + rot(rp) + ", o IBGE desenha floresta natural em <b>" + fmt.pct(I.forest_ibge, 1) + "</b> da área; o MapBiomas classifica como floresta <b>" + fmt.pct(I.forest_mb, 1) + "</b>.",
          "In the " + rot(rp) + " disc, IBGE draws natural forest over <b>" + fmt.pct(I.forest_ibge, 1) + "</b> of the area; MapBiomas classifies <b>" + fmt.pct(I.forest_mb, 1) + "</b> as forest."));
      },

      ibama: function (ctx, d) {
        var el = ctx.$("#fig-ibama"), E = (d.embargos || {}).features || [], A = (d.autos || {}).features || [];
        ctx.tiles({});
        ctx.vetores(vetBase(d, {
          embargos: { geojson: d.embargos, estilo: { color: "#ff7a00", weight: 1.5, fillColor: "#ff7a00", fillOpacity: 0.25 },
            popup: function (f) { var q = f.properties; return t("Embargo · ", "Embargo · ") + fmt.data(q.dat_embargo) + " · " + fmt.ha(Number(q.qtd_area_embargada)); } },
          autos: { geojson: d.autos, ponto: { radius: 4, color: "#fff", weight: 1, fillColor: "#c0392b", fillOpacity: 1 },
            popup: function (f) { var q = f.properties; return t("Auto de infração · ", "Infraction notice · ") + fmt.data(q.dat_hora_auto_infracao) + " · " + fmt.esc(q.des_status_formulario || ""); } }
        }));
        ctx.enquadrar([[d.bbox[1], d.bbox[0]], [d.bbox[3], d.bbox[2]]], { maxZoom: 13 });
        ctx.legendaMapa('<span><i style="background:#ff7a00"></i>' + t("área embargada", "embargoed area") + '</span><span><i style="background:#c0392b"></i>' + t("auto de infração", "infraction notice") + "</span>");
        // por ano, embargos e autos juntos
        var por = {};
        E.forEach(function (f) { var a = String(f.properties.dat_embargo || "").slice(0, 4); if (a) (por[a] = por[a] || 0), por[a]++; });
        A.forEach(function (f) { var a = String(f.properties.dat_hora_auto_infracao || "").slice(0, 4); if (a) (por[a] = por[a] || 0), por[a]++; });
        var anos = Object.keys(por).sort();
        if (anos.length) graf.colunas(el, { x: anos, valores: anos.map(function (a) { return por[a]; }), unidade: t("registros por ano (embargos + autos)", "records per year (embargoes + notices)"), dec: 0, cor: "#c0392b", rotular: anos.length < 16 });
        else el.innerHTML = '<p class="rp-fig-legenda">' + t("Nenhum embargo nem auto de infração no quadrado de 20 km em volta do ponto.", "No embargo or infraction notice in the 20 km square around the point.") + "</p>";
        var area = E.reduce(function (s, f) { return s + (Number(f.properties.qtd_area_embargada) || 0); }, 0);
        ctx.texto("ibama", (E.length || A.length) ? t(
          "No quadrado de 20 km em volta do ponto há <b>" + E.length + " áreas embargadas</b> (" + fmt.ha(area) + " nos termos de embargo) e <b>" + A.length +
          " autos de infração</b>, de " + (anos[0] || "—") + " a " + (anos[anos.length - 1] || "—") + ".",
          "The 20 km square around the point holds <b>" + E.length + " embargoed areas</b> (" + fmt.ha(area) + " in the embargo terms) and <b>" + A.length +
          " infraction notices</b>, from " + (anos[0] || "—") + " to " + (anos[anos.length - 1] || "—") + ".")
          : t("Não há registro do IBAMA no quadrado de 20 km em volta do ponto.", "IBAMA has no record in the 20 km square around the point."));
        ctx.legendaFig(t("Os nomes de autuados e embargados não aparecem nesta página; estão nos serviços públicos do IBAMA e na camada do aplicativo.",
          "The names of those fined or embargoed are left off this page; they are in IBAMA's public services and in the app's layer."));
      },

      procedencia: function (ctx, d) {
        ctx.tiles({}); ctx.vetores({}); ctx.legendaMapa("");
        graf.tabela(ctx.$("#fig-procedencia"), {
          colunas: [{ rotulo: t("Análise", "Analysis") }, { rotulo: t("Fonte (asset)", "Source (asset)") }, { rotulo: t("Escala", "Scale"), n: true }, { rotulo: t("Calculado", "Computed"), n: true }],
          linhas: (d.procedencia || []).map(function (p) { return [fmt.esc(p.nome), '<code style="font-size:11px;overflow-wrap:anywhere">' + fmt.esc(p.dataset) + "</code>", p.escala_m ? p.escala_m + " m" : "—", fmt.data(p.calculado_em)]; }),
          nota: t("Embargos e autos vêm, a cada consulta, dos serviços geográficos públicos do IBAMA; os conglomerados, do catálogo do IFN guardado no aplicativo.",
            "Embargoes and notices come, at each query, from IBAMA's public map services; the plots come from the inventory catalogue stored in the app.")
        });
        var n = (d.procedencia || []).length;
        ctx.texto("procedencia", t(
          "Para este ponto foram " + n + " consultas ao Earth Engine e duas ao IBAMA, no cálculo de " + fmt.dataHora(d.gerado_em) + ".",
          "This point took " + n + " Earth Engine queries and two IBAMA queries, in the run of " + fmt.dataHora(d.gerado_em) + "."));
      }
    }
  });
})();
