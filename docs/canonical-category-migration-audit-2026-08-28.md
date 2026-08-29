# Auditoría de migración canónica de categorías — 2026-08-28

Contrato de salida: `shared/public-category-taxonomy.json`. Las categorías de los
datasets de ciudad son vocabularios de origen, no autoridades públicas finales.
El conjunto histórico solicitado contiene 37 eventos futuros publicables: 16 de
Valparaíso/Viña con `otros` y 21 de Gijón con `actividad-panorama` o `cultura`.
Los tres programas genéricos se conservan fuera del gate estricto sólo porque
son contenedores `multi_day` con evidencia estructural de programa. `event_type`
por sí solo no exime: un evento fechado disfrazado como programa se bloquea.

| ID | Ciudad | Fuente | Título | Actual | Evidencia oficial | Propuesta | Confianza | Acción |
|---|---|---|---|---|---|---|---|---|
| agenda_6a62b556b781a210a35f6599 | Valparaíso | casa_cultura_valparaiso | El Mesón Nerudiano (Dominica 35, Recoleta) | otros | https://www.instagram.com/p/DcGo3vAumzV/; dos encuentros, geografía Recoleta/Valparaíso incompatible y segundo segmento truncado | cuarentena | high | excluded: multi_event_geography_conflict_with_truncated_segment |
| agenda_a336722c8e43e639f7d9891b | Viña del Mar | enjoy_vina | Nos vemos para juntos divertirnos y reírnos | otros | https://www.instagram.com/p/DcJ_ZpEiC7E/; descripción: humor/comedia | teatro | low | reclassified |
| agenda_20020b2f753b3f7375340f2d | Valparaíso | trotamundosvalpo | Cachate la fecha que te traigo! | otros | https://www.instagram.com/p/DcR5QT4xSqS/; descripción: rock/punk | musica | low | reclassified |
| agenda_6467e133788da5112c653367 | Viña del Mar | el_pasaje_cafe_vina | Las bases en historia destacada ! | otros | https://www.instagram.com/p/DccS2CzlOLs/; cierre de edición de “SE BUSCA POETA” | no-evento | high | excluded: call_for_submissions_deadline_not_event |
| agenda_rioja_20260828_consome | Viña del Mar | museo_palacio_rioja | Presentación libro // “Consomé Punk” | otros | https://visitavina.munivina.cl/actividades/; título: presentación de libro | literatura | high | reclassified |
| agenda_8c69cd737b4fcccce0fc4498 | Viña del Mar | el_pasaje_cafe_vina | encuentro pasajero con Caro de la Muela | otros | https://www.instagram.com/p/DcY0dHqFmqi/; encuentro con “charlita”, 28-08 20:00 | charlas-conferencias | medium | reclassified |
| agenda_72a7926be460ab979bf2cab9 | Viña del Mar | culturasvina | Tercer Encuentro de Bibliotecas Comunitarias de Viña del Mar | otros | https://www.instagram.com/p/DcMg2ypPyyA/; descripción: literatura/lectura | literatura | low | reclassified |
| agenda_272b3673c529d095127ade00 | Valparaíso | pcdv | DDHH “10 años resistiendo memoria | otros | https://parquecultural.cl/events/ddhh-10-anos-resistiendo-memoria/; descripción: exposición/muestra | exposiciones | low | reclassified |
| agenda_ce7998cb583f845825dcf72b | Valparaíso | pcdv | Literatura Presentación del libro “Ciudad de tinta y viento | otros | https://parquecultural.cl/events/literatura-presentacion-del-libro-ciudad-de-tinta-y-viento/; título: presentación de libro | literatura | high | reclassified |
| agenda_5c73be2934bf553e6bf2a663 | Viña del Mar | ipanema_club_vina | Brasil en ipanema club | otros | https://www.instagram.com/p/DcUvWnMOvy2/; samba y batucada en vivo, 05-09 20:00 | musica | medium | reclassified |
| agenda_c6717d0ce3951fa0b7128101 | Viña del Mar | enjoy_vina | Viña Classic Enjoy en Enjoy Viña del Mar | otros | https://www.puntoticket.com/evento/WIC110; descripción: música | musica | low | reclassified |
| agenda_d09f5a9206985455342c5be8 | Viña del Mar | enjoy_vina | Junto a Enjoy Viña queremos regalarte una escapada para dos | otros | https://www.instagram.com/p/DckMq3do_qj/; compartir, etiquetar y participar por estadía | no-evento | high | excluded: promotional_giveaway_not_attendance_event |
| agenda_d222f814bfe6ed49899ad8a9 | Viña del Mar | estadio_espanol_recreo | La guerra en el desierto | otros | https://www.instagram.com/p/DchYNRbjg6F/; ciclo de charlas, investigador, 29-09 19:00 | charlas-conferencias | medium | reclassified |
| agenda_78dd39a7a0a93ff6a4e635e9 | Valparaíso | trotamundosvalpo | Les gusta a trotamundosvalpo y otros | otros | https://www.instagram.com/p/DckIcqcx1pJ/; descripción: rock/punk | musica | low | reclassified |
| agenda_0dd975abf2e4c696dad55cfd | Viña del Mar | enjoy_vina | Alex Ubago en Enjoy Viña del Mar | otros | https://www.puntoticket.com/evento/SWG169; descripción: música/rock | musica | medium | reclassified |
| agenda_882086e19d7d4ca2b6c1bf9b | Viña del Mar | enjoy_vina | Los Jaivas 2026 Gira 45 años alturas de Macchu Picchu en Enjoy Coquimbo | otros | https://www.puntoticket.com/evento/PPR034; título y descripción: gira/música | musica | high | reclassified |
| gijon_bioparc_acuario_gijon_b0084910f667659a | Gijón | bioparc_acuario_gijon | Visita guiada Zonas Técnicas – especial verano | actividad-panorama | https://acuariogijon.es/actividad/visita-guiada-zonas-tecnicas-verano/; visita guiada | cursos-talleres-campus | high | reclassified |
| gijon_bioparc_acuario_gijon_e547a3965dc3cd95 | Gijón | bioparc_acuario_gijon | Alimentación del Gran Oceanario | actividad-panorama | https://acuariogijon.es/actividad/alimentacion-del-gran-oceanario/; calendario oficial de actividades y talleres | cursos-talleres-campus | low | reclassified |
| gijon_bioparc_acuario_gijon_6251cb23fc69821d | Gijón | bioparc_acuario_gijon | Encuentro Educativo Tiburones | actividad-panorama | https://acuariogijon.es/actividad/encuentro-educativo-tiburones/; encuentro educativo | cursos-talleres-campus | high | reclassified |
| gijon_bioparc_acuario_gijon_3c5c4264031ddc97 | Gijón | bioparc_acuario_gijon | Encuentro Educativo en Oceanario | actividad-panorama | https://acuariogijon.es/actividad/encuentro-educativo-sobre-tiburones/; encuentro educativo | cursos-talleres-campus | high | reclassified |
| gijon_bioparc_acuario_gijon_e3296706a06801b5 | Gijón | bioparc_acuario_gijon | Visita especial tiburones: desmontando mitos | actividad-panorama | https://acuariogijon.es/actividad/visita-especial-tiburones-desmontando-mitos/; visita especial | cursos-talleres-campus | high | reclassified |
| gijon_laboral_centro_arte_9f6a290c2e4567b1 | Gijón | laboral_centro_arte | Documenta Asturies | cultura | https://laboralcentrodearte.org/es/actividades/documenta-asturies/; descripción: exposición | exposiciones | low | reclassified |
| agenda_gijon_c9a0b2bf86f96469 | Gijón | centro_cultura_antiguo_instituto | Xornaes Culturales Asturies en Guerra - 90 años: La Batalla por Gijón | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; título: xornaes culturales | charlas-conferencias | high | reclassified |
| agenda_gijon_b4470d40a14cd11b | Gijón | gijon_opendata_events | Conferencia: “LA ENERGÍA DEL SIGLO XXI” REALIDAD Y DESEOS | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; tag/título: conferencia | charlas-conferencias | high | reclassified |
| agenda_gijon_efb5524a8f0df186 | Gijón | centro_cultura_antiguo_instituto | Conferencia: Unidad y cohesión social ante los riesgos que corren | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; tag/título: conferencia | charlas-conferencias | high | reclassified |
| agenda_gijon_97e380986a675043 | Gijón | gijon_opendata_events | Conferencia: HÓRREOS Y PANERAS ASTURIANAS CINCO SIGLOS DE VIDA | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; tag/título: conferencia | charlas-conferencias | high | reclassified |
| agenda_gijon_05707ecf807dcd06 | Gijón | centro_cultura_antiguo_instituto | Presentación del Libro: “De África a su Diáspora” | cultura | https://drupal.gijon.es/es/presentacion-del-libro-de-africa-su-diaspora-seleccion-de-textos-y-guias-de-lectura; título/tags: libro/literatura | literatura | high | reclassified |
| agenda_gijon_5c2647e4ac03b04a | Gijón | gijon_opendata_events | Encuentros Poéticos en el Antiguo Instituto | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; descripción: poesía | literatura | low | reclassified |
| gijon_teatro_albeniz_gijon_ee2c59319ca5d5c3 | Gijón | teatro_albeniz_gijon | Fiesta Blanca 2026- Regreso a los 80 | actividad-panorama | https://www.teatroalbenizgijon.com/evento/fiesta-blanca-2026-regreso-a-los-80/; descripción oficial “música, copas y baile”; label oficial preservado | musica | medium; score 3 | reclassified |
| agenda_gijon_925dedae6c5277fd | Gijón | centro_cultura_antiguo_instituto | Presentación del Libro: MARIPOSA DE LA NOCHE | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; título/tags: libro/literatura | literatura | high | reclassified |
| agenda_gijon_8e2c9e268d9924d8 | Gijón | centro_cultura_antiguo_instituto | JORNADAS: COMADRES DE ORO INVITADAS | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; tag/descripción: conferencia/jornadas | charlas-conferencias | high | reclassified |
| agenda_gijon_7c578c6ad675e2ed | Gijón | centro_cultura_antiguo_instituto | Conferencia: La huella de Cervantes en la narrativa actual | cultura | https://drupal.gijon.es/es/conferencia-la-huella-de-cervantes-en-la-narrativa-actual; título/tag: conferencia | charlas-conferencias | high | reclassified |
| agenda_gijon_028acb09de6a6827 | Gijón | centro_cultura_antiguo_instituto | Presentación del Libro: “En la Escuela del Capitalismo” | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; título/tags: libro/literatura | literatura | high | reclassified |
| agenda_gijon_704d1c12fe9a0424 | Gijón | centro_cultura_antiguo_instituto | Presentación del Libro: Gaza, un genocidio televisado | cultura | https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML; título/tags: libro/literatura | literatura | high | reclassified |
| agenda_gijon_56958d5f043d36de | Gijón | centro_cultura_antiguo_instituto | Encuentro Internacional de Fotoperiodismo de Asturias | cultura | https://fotoperiodismoasturias.org/ descubierta desde ficha municipal; talleres + encuentros educativos + formación + aprender = 8; diálogo + reflexión = 2 | cursos-talleres-campus | medium | reclassified |
| gijon_camara_recinto_ferial_gijon_f998a19e7c34490c | Gijón | camara_recinto_ferial_gijon | EL GRAN SHOWMAN | actividad-panorama | https://recintoferialasturias.camaragijon.es/es/cargarAplicacionAgenda.do?&anio=2026&identificador=1124&proximosEventos=1; señal oficial de musical escénico | teatro | high | reclassified |
| gijon_camara_recinto_ferial_gijon_a68bdf785ac4055a | Gijón | camara_recinto_ferial_gijon | HOMENAJE DIRE STRAITS | actividad-panorama | https://recintoferialasturias.camaragijon.es/es/cargarAplicacionAgenda.do?&anio=2026&identificador=1082&proximosEventos=1; señal oficial musical | musica | high | reclassified |

## Resultado

- Conservados dentro del conjunto de 37: 0.
- Aliases normalizados dentro del conjunto de 37: 0.
- Reclasificados con evidencia: 34 (Valparaíso/Viña 13; Gijón 21).
- Excluidos justificadamente: 3 (Valparaíso/Viña 3).
- Bloqueados: 0.

La migración general también conserva categorías temáticas válidas y normaliza
aliases registrados fuera de este subconjunto histórico. Ningún bloqueo se
resuelve por ID, título, fuente o ciudad. Las tres exclusiones generan inventario
y receipt de cuarentena; no desaparecen silenciosamente.

## Programas genéricos fuera del gate

- `Centex – Cartelera Agosto`: `content_kind=program`, contenedor oficial del mes,
  `event_type=program`, `schedule.mode=multi_day`; no representa una asistencia única.
- `Valparaíso Profundo – Programación Agosto`: `content_kind=program`, cobertura
  mensual oficial, `event_type=program`, `schedule.mode=multi_day`.
- `Gijón Verano: inscripciones`: `content_kind=program`, periodo municipal de
  inscripciones, clasificación editorial `program` y ventana multidía.

Los `dated_event` y `long_running_event` siguen en alcance. La exención requiere
simultáneamente tipo programa, forma multidía y señal de contenedor; existe una
regresión que bloquea un evento fechado etiquetado artificialmente como programa.
