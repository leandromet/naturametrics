/* Naturametrics — demonstração em rolagem (/demonstracao).
 *
 * Os números vêm de /_demonstracao/naturametrics.json (services/demonstracao.py),
 * montado pelos mesmos serviços que a interface usa ao clicar num ponto. Este
 * arquivo só decide o que cada passo mostra; nenhum valor é escrito à mão.
 */
(function () {
  var R = window.Reportagem, fmt = R.fmt, graf = R.graf;

  var COR_RAIO = { "0.5": "#d98324", "1": "#b5651d", "2": "#1f6f4a", "5": "#4f8f6f", "10": "#9cc2ac" };
  var COR_PERDA = "#e5484d", COR_GANHO = "#30a46c";
  // os grupos de services/ibge_vegetation.bucket_matrix (aqui sem rótulos no pacote)
  var GRUPO_IBGE = { natural_forest: "Natural — Floresta", natural_non_forest: "Natural — Não floresta",
    anthropic_forest: "Antrópico — Floresta plantada", anthropic_regrowth: "Antrópico — Vegetação secundária",
    anthropic_non_forest: "Antrópico — Agropecuária/Urbano", water: "Água", other: "Outros/sem dados" };

  function rot(r) { return fmt.n(Number(r), Number(r) < 1 ? 1 : 0) + " km"; }
  function principal(d) { return String(d.raio_principal).replace(/\.0$/, ""); }
  function discos(d, so) {
    return { type: "FeatureCollection", features: d.buffers.features.filter(function (f) {
      return f.properties.role === "buffer" && (!so || so.indexOf(String(f.properties.radius_km).replace(/\.0$/, "")) >= 0);
    }) };
  }
  function pontoGeo(d) { return { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [d.ponto.lon, d.ponto.lat] } }; }
  function vetBase(d, extra) {
    var v = {
      discos: { geojson: discos(d), estilo: function (f) { var k = String(f.properties.radius_km).replace(/\.0$/, ""); return { color: COR_RAIO[k] || "#fff", weight: 1.5, dashArray: "5 4", fillOpacity: 0 }; } },
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
    return Object.keys(z).map(function (c) { return { id: c, ha: z[c][i] || 0, nome: h.classes[c].nome, cor: h.classes[c].cor }; })
      .filter(function (x) { return x.ha > 0; }).sort(function (a, b) { return b.ha - a.ha; });
  }
  function legendaClasses(d, i, raio) {
    return "<b>MapBiomas " + d.historico.anos[i] + " · no disco de " + rot(raio) + "</b>" + classesNoAno(d, raio, i).slice(0, 6).map(function (c) {
      return '<span><i style="background:' + c.cor + '"></i>' + fmt.esc(c.nome) + "</span>";
    }).join("");
  }
  function camada(d, k, op) { var c = d.camadas[k]; return c ? Object.assign({}, c, op ? { opacity: op } : {}) : null; }
  function faltou(el, nome) { el.innerHTML = '<p class="rp-fig-estado erro">' + nome + ' não respondeu neste cálculo <span class="selo ausente">ausente</span></p>'; }
  function nomeLugar(d) {
    var p = d.ponto;
    return p.conglomerado ? p.conglomerado + (p.municipio ? " · " + p.municipio + "/" + p.uf : "") : fmt.n(p.lat, 4) + ", " + fmt.n(p.lon, 4);
  }
  function linkApp(d) {
    var p = d.ponto;
    return p.conglomerado ? "/?ifn=" + encodeURIComponent(p.conglomerado) : "/?lat=" + p.lat + "&lon=" + p.lon;
  }

  R.iniciar({
    dados: function (ctx) {
      var q = [], ifn = ctx.params.get("ifn"), lat = ctx.params.get("lat"), lon = ctx.params.get("lon");
      if (ifn) q.push("ifn=" + encodeURIComponent(ifn));
      else if (lat && lon) q.push("lat=" + encodeURIComponent(lat), "lon=" + encodeURIComponent(lon));
      return "/_demonstracao/naturametrics.json" + (q.length ? "?" + q.join("&") : "");
    },
    centro: [-12, -55], zoom: 5,

    aoCarregar: function (ctx, d) {
      var p = d.ponto, rp = principal(d), h = d.historico;
      var nat = h ? nativaPct(d, rp) : [];
      var mud = d.mudanca && d.mudanca.raios[rp];
      var nIbama = ((d.embargos || {}).features || []).length + ((d.autos || {}).features || []).length;
      ctx.preencher({
        "n-nativa0": h ? fmt.pct(nat[0]) : "—",
        "n-nativa0-rot": h ? "vegetação nativa no disco de " + rot(rp) + " em " + h.anos[0] + ' <span class="selo real">real</span>' : "vegetação nativa no primeiro ano",
        "n-nativa1": h ? fmt.pct(nat[nat.length - 1]) : "—",
        "n-nativa1-rot": h ? "no mesmo disco em " + h.anos[h.anos.length - 1] + ' <span class="selo real">real</span>' : "vegetação nativa no último ano",
        "n-perda": mud ? fmt.ha(mud.loss_ha) : "—",
        "n-perda-rot": "de vegetação nativa perdida no disco desde " + (d.mudanca ? d.mudanca.de : 2008) + ' <span class="selo real">real</span>',
        "n-ibama": fmt.n(nIbama)
      });
      ctx.$("#topo-exemplo").textContent = nomeLugar(d);
      ctx.$("#link-app").href = linkApp(d); ctx.$("#cta-app").href = linkApp(d);
      ctx.$("#rp-fig-url").textContent = "naturametrics.umaterra.com.br" + linkApp(d);
      ctx.$("#abertura-exemplo").innerHTML = (d.exemplo_padrao ? "Exemplo desta página: " : "Ponto escolhido: ") + "<b>" + fmt.esc(nomeLugar(d)) + "</b>" +
        (p.bioma ? ", bioma " + fmt.esc(p.bioma) : "") + ". Calculado pelos serviços do aplicativo em " + fmt.dataHora(d.gerado_em) + (d.exemplo_padrao ? " e guardado com esta página." : " (o resultado fica guardado por algumas horas).");
      var erros = Object.keys(d.erros || {});
      ctx.$("#fim-extra").innerHTML = erros.length
        ? "Neste cálculo não responderam: <b>" + erros.map(fmt.esc).join(", ") + "</b>. Os passos correspondentes dizem o que faltou."
        : "Todas as análises responderam no cálculo de " + fmt.dataHora(d.gerado_em) + ".";
      ctx.texto("ponto", "Aqui o ponto é " + (p.conglomerado ? "o conglomerado <b>" + fmt.esc(p.conglomerado) + "</b>, em " + fmt.esc(p.municipio || "—") + "/" + fmt.esc(p.uf || "—") : "a coordenada pedida no endereço") +
        ", em <b>" + fmt.n(Math.abs(p.lat), 4) + "°" + (p.lat < 0 ? "S" : "N") + " " + fmt.n(Math.abs(p.lon), 4) + "°" + (p.lon < 0 ? "O" : "L") + "</b>.");
      var vizinhos = ((d.ifn || {}).features || []).length;
      ctx.texto("ifn", vizinhos > 1 ? "No quadrado de 20 km em volta deste ponto há <b>" + vizinhos + " conglomerados</b>; no mapa, em branco." :
        "A grade do IFN é larga: no quadrado de 20 km em volta deste ponto, " + (vizinhos === 1 ? "este é o único conglomerado." : "não há conglomerado."));
      ctx.texto("discos", "Do menor ao maior: " + d.raios.map(function (r) { return "<b>" + fmt.ha(d.areas_ha[String(r).replace(/\.0$/, "")]) + "</b>"; }).join(", ") +
        ". O disco de 10 km tem 400 vezes a área do de 0,5 km: o raio muda a escala da pergunta.");
    },

    passos: {
      ponto: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores({ ponto: vetBase(d).ponto });
        ctx.enquadrar(discos(d, ["1"]), { maxZoom: 14 });
        ctx.legendaMapa("");
        var p = d.ponto;
        ctx.$("#fig-ponto").innerHTML = '<dl class="rp-ficha"><dt>Origem</dt><dd>' + fmt.esc(p.origem) + "</dd>" +
          (p.conglomerado ? "<dt>Conglomerado</dt><dd>" + fmt.esc(p.conglomerado) + "</dd><dt>Município</dt><dd>" + fmt.esc(p.municipio) + "/" + fmt.esc(p.uf) + "</dd><dt>Bioma</dt><dd>" + fmt.esc(p.bioma) + "</dd>" : "") +
          "<dt>Coordenada</dt><dd>" + fmt.n(p.lat, 5) + ", " + fmt.n(p.lon, 5) + "</dd></dl>";
      },

      ifn: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores({
          ifn: { geojson: d.ifn, ponto: function (f) { var eu = f.properties.conglomerado === d.ponto.conglomerado; return { radius: eu ? 8 : 5, color: "#fff", weight: 2, fillColor: eu ? "#d98324" : "#ffffff", fillOpacity: eu ? 1 : 0.85 }; },
            popup: function (f) { return fmt.esc(f.properties.conglomerado) + " · " + fmt.esc(f.properties.municipio || "") + " · " + fmt.esc(f.properties.bioma || ""); } }
        });
        ctx.enquadrar([[d.bbox[1], d.bbox[0]], [d.bbox[3], d.bbox[2]]], { maxZoom: 12 });
        ctx.legendaMapa('<span><i style="background:#d98324"></i>este conglomerado</span><span><i style="background:#fff;border:1px solid #9aa8a1"></i>outros conglomerados</span>');
        var fs = ((d.ifn || {}).features || []);
        graf.tabela(ctx.$("#fig-ifn"), {
          colunas: [{ rotulo: "Conglomerado" }, { rotulo: "Município" }, { rotulo: "Bioma" }],
          linhas: fs.slice(0, 6).map(function (f) { var q = f.properties; return [(q.conglomerado === d.ponto.conglomerado ? "<b>" : "") + fmt.esc(q.conglomerado) + (q.conglomerado === d.ponto.conglomerado ? "</b>" : ""), fmt.esc(q.municipio || "—") + "/" + fmt.esc(q.uf || ""), fmt.esc(q.bioma || "")]; }),
          nota: "17.479 pontos no catálogo do aplicativo, com as coordenadas publicadas pelo Serviço Florestal Brasileiro."
        });
      },

      discos: function (ctx, d) {
        ctx.tiles({});
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa(d.raios.map(function (r) { var k = String(r).replace(/\.0$/, ""); return '<span><i style="background:' + COR_RAIO[k] + '"></i>' + rot(r) + "</span>"; }).join(""));
        graf.tabela(ctx.$("#fig-discos"), {
          colunas: [{ rotulo: "Raio" }, { rotulo: "Área do disco", n: true }, { rotulo: "× o de 0,5 km", n: true }],
          linhas: d.raios.map(function (r) { var k = String(r).replace(/\.0$/, ""); return [graf.qd(COR_RAIO[k]) + rot(r), fmt.ha(d.areas_ha[k]), fmt.n(d.areas_ha[k] / d.areas_ha["0.5"], 0)]; })
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
        var series = Object.keys(z).map(function (c) { return { rotulo: h.classes[c].nome, cor: h.classes[c].cor, valores: z[c] }; })
          .sort(function (a, b) { return b.valores[ultimo] - a.valores[ultimo]; });
        graf.empilhado(el, { anos: h.anos, series: series, unidade: "ha no disco de " + rot(rp), dec: 0, marcas: [{ ano: 2008, rotulo: "2008" }] });
        var c0 = classesNoAno(d, rp, 0)[0], cf = classesNoAno(d, rp, ultimo)[0], troca = null;
        for (var i = 1; i <= ultimo; i++) { var ci = classesNoAno(d, rp, i)[0]; if (ci && c0 && ci.id !== c0.id) { troca = { ano: h.anos[i], c: ci }; break; } }
        ctx.texto("historia", "No disco de " + rot(rp) + ", a maior classe em " + h.anos[0] + " era <b>" + fmt.esc(c0.nome) + "</b> (" + fmt.ha(c0.ha) + "). " +
          (troca ? "Em <b>" + troca.ano + "</b> ela é ultrapassada por <b>" + fmt.esc(troca.c.nome) + "</b>. " : "Ela continua sendo a maior até o fim da série. ") +
          "Em " + h.anos[ultimo] + ", a maior é <b>" + fmt.esc(cf.nome) + "</b>, com " + fmt.ha(cf.ha) + ".");
      },

      raios: function (ctx, d) {
        var el = ctx.$("#fig-raios"), h = d.historico;
        if (!h) return faltou(el, "O MapBiomas");
        ctx.tiles({ mb: camada(d, "mb_" + h.anos[0], 0.85) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa(legendaClasses(d, 0, "10"));
        var series = d.raios.map(function (r) { var k = String(r).replace(/\.0$/, ""); return { rotulo: rot(r), cor: COR_RAIO[k], valores: nativaPct(d, k), espessura: k === "0.5" ? 3 : 2 }; });
        graf.linhas(el, { x: h.anos, series: series, unidade: "% de vegetação nativa no disco", min: 0, max: 100, marcas: [{ x: 2008, rotulo: "2008" }] });
        // em que ano cada disco passou abaixo de metade nativa
        var meio = series.map(function (s) { for (var i = 0; i < s.valores.length; i++) if (s.valores[i] !== null && s.valores[i] < 50) return { r: s.rotulo, ano: h.anos[i] }; return { r: s.rotulo, ano: null }; });
        var cruzaram = meio.filter(function (m) { return m.ano; });
        ctx.texto("raios", cruzaram.length
          ? "Ano em que cada disco ficou com menos da metade de vegetação nativa: " + meio.map(function (m) { return m.r + " → <b>" + (m.ano || "nunca") + "</b>"; }).join(", ") + "."
          : "Nenhum dos discos chegou a ter menos da metade de vegetação nativa na série.");
      },

      pixel: function (ctx, d) {
        var el = ctx.$("#fig-pixel"), px = d.pixel, h = d.historico;
        if (!px) return faltou(el, "A série do pixel");
        ctx.tiles({ mb: camada(d, "mb_" + px[px.length - 1].ano, 0.85) });
        ctx.vetores(vetBase(d));
        ctx.centro([d.ponto.lat, d.ponto.lon], 16);
        ctx.legendaMapa("<b>O ponto sobre o pixel de 30 m do último ano</b>");
        // uma faixa de anos, uma célula por ano, na cor da classe do pixel
        // margem de 24 nos dois lados para o primeiro e o último ano não saírem do desenho
        var n = px.length, w = 712 / n, x0 = 24, s = "", trocas = [];
        px.forEach(function (x, i) {
          var cor = (h && h.classes[String(x.classe)] || {}).cor || "#9aa8a1";
          s += '<rect x="' + (x0 + i * w) + '" y="20" width="' + (w - 1) + '" height="46" fill="' + cor + '"><title>' + x.ano + ": " + fmt.esc(x.nome) + "</title></rect>";
          if (i % 5 === 0 || i === n - 1) s += '<text class="eixo" x="' + (x0 + i * w + w / 2) + '" y="84" text-anchor="middle">' + x.ano + "</text>";
          if (i > 0 && x.classe !== px[i - 1].classe) trocas.push(x);
        });
        var vistas = {}; px.forEach(function (x) { vistas[x.nome] = (h && h.classes[String(x.classe)] || {}).cor || "#9aa8a1"; });
        el.innerHTML = '<svg class="rp-sv" viewBox="0 0 760 92" role="img" aria-label="Classe do pixel por ano">' + s + "</svg>" +
          graf.legenda(Object.keys(vistas).map(function (k) { return { rotulo: k, cor: vistas[k] }; }));
        ctx.texto("pixel", trocas.length
          ? "Neste pixel o classificador mudou de classe <b>" + trocas.length + " vez" + (trocas.length > 1 ? "es" : "") + "</b>: " + trocas.slice(0, 4).map(function (x) { return x.ano + " (" + fmt.esc(x.nome) + ")"; }).join(", ") + (trocas.length > 4 ? "…" : "") + "."
          : "Neste pixel, o classificador viu a mesma classe nos " + n + " anos: <b>" + fmt.esc(px[0].nome) + "</b>.");
      },

      mudanca: function (ctx, d) {
        var el = ctx.$("#fig-mudanca"), M = d.mudanca;
        if (!M) return faltou(el, "A máscara de mudança");
        ctx.tiles({ mud: camada(d, "mudanca", 0.9) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa("<b>Mudança " + M.de + " → " + M.ate + "</b>" + '<span><i style="background:' + COR_PERDA + '"></i>vegetação nativa perdida</span><span><i style="background:' + COR_GANHO + '"></i>regeneração</span>');
        var linhas = [];
        d.raios.forEach(function (r) {
          var k = String(r).replace(/\.0$/, ""), x = M.raios[k]; if (!x) return;
          linhas.push({ rotulo: rot(r) + " · perda", valor: x.loss_ha, cor: COR_PERDA, texto: fmt.ha(x.loss_ha) });
          linhas.push({ rotulo: rot(r) + " · regeneração", valor: x.gain_ha, cor: COR_GANHO, texto: fmt.ha(x.gain_ha) });
        });
        graf.barrasH(el, { linhas: linhas, xRotulo: 190 });
        var rp = principal(d), x = M.raios[rp];
        ctx.texto("mudanca", x ? "No disco de " + rot(rp) + ": <b>" + fmt.ha(x.loss_ha) + "</b> de vegetação nativa em " + M.de + " deixaram de ser nativos até " + M.ate +
          ", e <b>" + fmt.ha(x.gain_ha) + "</b> voltaram. Ficaram nativos, nos dois anos, " + fmt.ha(x.stable_ha) + "." : "");
        ctx.legendaFig("A camada é uma triagem: aponta áreas para olhar, não constata ilegalidade. O Código Florestal decide pela data, pelo imóvel e pelas autorizações, que o satélite não vê.");
      },

      idade: function (ctx, d) {
        var el = ctx.$("#fig-idade"), I = d.idade, rp = principal(d);
        if (!I) return faltou(el, "A idade da vegetação");
        ctx.tiles({ mb: camada(d, "mb_" + d.historico.anos[d.historico.anos.length - 1], 0.6) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, [rp]), { maxZoom: 13 });
        ctx.legendaMapa("");
        var fx = I.faixas[rp] || [], res = I.resumo[rp] || {};
        graf.barrasH(el, { linhas: fx.map(function (f) { return { rotulo: f.faixa, valor: f.ha, cor: f.cor, texto: fmt.ha(f.ha) }; }), xRotulo: 230 });
        var serie = d.idade_ponto || [];
        if (serie.length) {
          var box = document.createElement("div"); el.appendChild(box);
          graf.linhas(box, { x: serie.map(function (x) { return x.ano; }), series: [{ rotulo: "idade no pixel do ponto (anos)", cor: "#1f6f4a", valores: serie.map(function (x) { return x.idade; }), pontos: true }], min: 0, altura: 170, unidade: "anos" });
        }
        ctx.texto("idade", "No disco de " + rot(rp) + " há <b>" + fmt.ha(res.total_natural_area_ha) + "</b> de vegetação hoje. Desse total, <b>" + fmt.pct(res.censored_pct, 1) +
          "</b> não tem idade conhecida (" + fmt.esc(res.censored_label || "") + "); a parte datada, " + fmt.ha(res.dated_area_ha) + ", tem mediana de <b>" + fmt.n(res.median_dated_age) + " anos</b>.");
      },

      metricas: function (ctx, d) {
        var el = ctx.$("#fig-metricas"), M = d.metricas;
        ctx.tiles({}); ctx.vetores({}); ctx.legendaMapa("");
        if (!M) return faltou(el, "As métricas de paisagem");
        graf.tabela(el, {
          colunas: [{ rotulo: "Raio" }, { rotulo: "Fragmentos", n: true }, { rotulo: "Por 100 ha", n: true }, { rotulo: "Borda (m/ha)", n: true }, { rotulo: "Shannon", n: true }],
          linhas: M.map(function (m) { return [rot(m.radius_km), fmt.n(m.patches), fmt.n(100 * m.patches / m.area_ha, 1), fmt.n(m.edge_density, 1), fmt.n(m.shannon, 2)]; }),
          nota: "Fragmentos: manchas contínuas de uma mesma classe (vizinhança de 8 pixels), MapBiomas " + d.historico.anos[d.historico.anos.length - 1] + "."
        });
        el.insertAdjacentHTML("beforeend", '<p class="rp-aviso"><b>Limite do cálculo.</b> Os componentes conectados do Earth Engine param em 1.024 pixels (~92 ha). ' +
          "Uma mancha maior que isso é cortada, então o <i>maior fragmento</i> e a <i>malha efetiva</i> do aplicativo ficam limitados a esse teto e não aparecem aqui como medida. " +
          "O aplicativo registra o teto na procedência de cada cálculo.</p>");
        var a = M[0], b = M[M.length - 1];
        ctx.texto("metricas", "Do disco de " + rot(a.radius_km) + " ao de " + rot(b.radius_km) + ", a densidade de fragmentos vai de <b>" + fmt.n(100 * a.patches / a.area_ha, 1) +
          "</b> para <b>" + fmt.n(100 * b.patches / b.area_ha, 1) + "</b> por 100 ha, e a borda de " + fmt.n(a.edge_density, 0) + " para " + fmt.n(b.edge_density, 0) + " m/ha.");
      },

      biomassa: function (ctx, d) {
        var el = ctx.$("#fig-biomassa"), B = d.biomassa, rp = principal(d);
        if (!B) return faltou(el, "O ESA CCI");
        ctx.tiles({ bio: camada(d, "biomassa", 0.75) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa('<b>ESA CCI · biomassa acima do solo</b><span><i class="g" style="background:linear-gradient(90deg,#fff,#008000)"></i>baixa → alta</span>');
        var serie = B[rp] || [], anos = serie.map(function (x) { return x.ano; });
        graf.linhas(el, {
          x: anos, unidade: "Mg/ha", min: 0,
          faixa: { min: serie.map(function (x) { return Math.max(0, x.mgha - x.sd); }), max: serie.map(function (x) { return x.mgha + x.sd; }), cor: "#4f8f6f" },
          series: d.raios.filter(function (r) { var k = String(r).replace(/\.0$/, ""); return B[k] && (k === rp || k === "0.5" || k === "10"); }).map(function (r) {
            var k = String(r).replace(/\.0$/, ""), m = {}; B[k].forEach(function (x) { m[x.ano] = x.mgha; });
            return { rotulo: rot(r) + (k === rp ? " (faixa: ± 1 desvio-padrão)" : ""), cor: COR_RAIO[k], valores: anos.map(function (a) { return m[a]; }), pontos: true, espessura: k === rp ? 3 : 2 };
          })
        });
        if (serie.length) ctx.texto("biomassa", "No disco de " + rot(rp) + ", a média vai de <b>" + fmt.n(serie[0].mgha) + " Mg/ha</b> em " + serie[0].ano + " para <b>" + fmt.n(serie[serie.length - 1].mgha) +
          " Mg/ha</b> em " + serie[serie.length - 1].ano + ". O desvio-padrão médio do produto no disco é de ±" + fmt.n(serie.reduce(function (a, x) { return a + x.sd; }, 0) / serie.length) + " Mg/ha.");
      },

      ibge: function (ctx, d) {
        var el = ctx.$("#fig-ibge"), I = d.ibge, rp = principal(d);
        ctx.tiles({ ibge: camada(d, "ibge", 0.75) });
        ctx.vetores(vetBase(d));
        ctx.enquadrar(discos(d, ["10"]), { maxZoom: 13 });
        ctx.legendaMapa("<b>IBGE · vegetação, rasterizada</b>com a paleta do aplicativo");
        if (!I) return faltou(el, "O mapa do IBGE");
        var g = I.groups.filter(function (k) { return I.groups.some(function (m) { return (I.matrix[k] || {})[m] > 0.05 || (I.matrix[m] || {})[k] > 0.05; }); });
        graf.tabela(el, {
          colunas: [{ rotulo: "IBGE ↓ · MapBiomas →" }].concat(g.map(function (k) { return { rotulo: ((I.group_labels || GRUPO_IBGE)[k] || k).replace("Antrópico — ", "").replace("Natural — ", ""), n: true }; })),
          linhas: g.map(function (k) { return [fmt.esc((I.group_labels || GRUPO_IBGE)[k] || k)].concat(g.map(function (m) { var v = (I.matrix[k] || {})[m] || 0; return v > 0.05 ? (k === m ? "<b>" + fmt.pct(v, 1) + "</b>" : fmt.pct(v, 1)) : "·"; })); }),
          nota: "Parte do disco de " + rot(rp) + " em cada par de classes. A diagonal, em negrito, é onde os dois mapas concordam."
        });
        ctx.texto("ibge", "No disco de " + rot(rp) + ", o IBGE desenha floresta natural em <b>" + fmt.pct(I.forest_ibge, 1) + "</b> da área; o MapBiomas classifica como floresta <b>" + fmt.pct(I.forest_mb, 1) + "</b>.");
      },

      ibama: function (ctx, d) {
        var el = ctx.$("#fig-ibama"), E = (d.embargos || {}).features || [], A = (d.autos || {}).features || [];
        ctx.tiles({});
        ctx.vetores(vetBase(d, {
          embargos: { geojson: d.embargos, estilo: { color: "#ff7a00", weight: 1.5, fillColor: "#ff7a00", fillOpacity: 0.25 },
            popup: function (f) { var q = f.properties; return "Embargo · " + fmt.data(q.dat_embargo) + " · " + fmt.ha(Number(q.qtd_area_embargada)); } },
          autos: { geojson: d.autos, ponto: { radius: 4, color: "#fff", weight: 1, fillColor: "#c0392b", fillOpacity: 1 },
            popup: function (f) { var q = f.properties; return "Auto de infração · " + fmt.data(q.dat_hora_auto_infracao) + " · " + fmt.esc(q.des_status_formulario || ""); } }
        }));
        ctx.enquadrar([[d.bbox[1], d.bbox[0]], [d.bbox[3], d.bbox[2]]], { maxZoom: 13 });
        ctx.legendaMapa('<span><i style="background:#ff7a00"></i>área embargada</span><span><i style="background:#c0392b"></i>auto de infração</span>');
        // por ano, embargos e autos lado a lado
        var por = {};
        E.forEach(function (f) { var a = String(f.properties.dat_embargo || "").slice(0, 4); if (a) (por[a] = por[a] || { e: 0, a: 0 }).e++; });
        A.forEach(function (f) { var a = String(f.properties.dat_hora_auto_infracao || "").slice(0, 4); if (a) (por[a] = por[a] || { e: 0, a: 0 }).a++; });
        var anos = Object.keys(por).sort();
        if (anos.length) {
          graf.colunas(el, { x: anos, valores: anos.map(function (a) { return por[a].e + por[a].a; }), unidade: "registros por ano (embargos + autos)", dec: 0, cor: "#c0392b", rotular: anos.length < 16 });
        } else el.innerHTML = '<p class="rp-fig-legenda">Nenhum embargo nem auto de infração no quadrado de 20 km em volta do ponto.</p>';
        var area = E.reduce(function (s, f) { return s + (Number(f.properties.qtd_area_embargada) || 0); }, 0);
        ctx.texto("ibama", (E.length || A.length) ? "No quadrado de 20 km em volta do ponto há <b>" + E.length + " áreas embargadas</b> (" + fmt.ha(area) + " declarados nos termos) e <b>" + A.length +
          " autos de infração</b>, de " + (anos[0] || "—") + " a " + (anos[anos.length - 1] || "—") + "." : "Não há registro do IBAMA no quadrado de 20 km em volta do ponto.");
        ctx.legendaFig("Os nomes de autuados e embargados não aparecem nesta página; eles estão nos serviços públicos do IBAMA e na camada do aplicativo.");
      },

      procedencia: function (ctx, d) {
        ctx.tiles({}); ctx.vetores({}); ctx.legendaMapa("");
        graf.tabela(ctx.$("#fig-procedencia"), {
          colunas: [{ rotulo: "Análise" }, { rotulo: "Fonte (asset)" }, { rotulo: "Escala", n: true }, { rotulo: "Calculado", n: true }],
          linhas: (d.procedencia || []).map(function (p) { return [fmt.esc(p.nome), '<code style="font-size:11px;overflow-wrap:anywhere">' + fmt.esc(p.dataset) + "</code>", p.escala_m ? p.escala_m + " m" : "—", fmt.data(p.calculado_em)]; }),
          nota: "Embargos e autos vêm, a cada consulta, dos serviços geográficos públicos do IBAMA; os conglomerados, do catálogo do IFN guardado no aplicativo."
        });
        ctx.texto("procedencia", "Para este ponto foram " + (d.procedencia || []).length + " consultas ao Earth Engine e duas ao IBAMA, no cálculo de " + fmt.dataHora(d.gerado_em) + ".");
      }
    }
  });
})();
