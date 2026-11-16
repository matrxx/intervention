// Interventions C2RMF — comportements légers (la page fonctionne aussi sans JavaScript)
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // --- Formulaire de saisie : étendue du lieu, niveaux, salles, horaires
  const form = $('#form-intervention');
  if (form) {
    const portee = () => (form.querySelector('input[name="portee"]:checked') || {}).value;
    const majPortee = () => {
      const p = portee();
      $$('[data-portee]', form).forEach(el => { el.hidden = !el.dataset.portee.split(' ').includes(p); });
    };
    $$('input[name="portee"]', form).forEach(r => r.addEventListener('change', majPortee));
    majPortee();

    const niveaux = JSON.parse(($('#niveaux-par-zone') || {}).textContent || '{}');
    const zone = $('#id_zone'), niv = $('#id_niveau');
    const majNiveaux = () => {
      if (!zone || !niv) return;
      const liste = niveaux[zone.value] || [];
      const actuel = niv.value;
      niv.innerHTML = '';
      liste.forEach(n => { const o = document.createElement('option'); o.value = o.textContent = n; if (n === actuel) o.selected = true; niv.appendChild(o); });
    };
    if (zone) { zone.addEventListener('change', majNiveaux); majNiveaux(); }

    const q = $('#recherche-salle'), list = $('#liste-salles'), picked = $('#salles-choisies');
    const majChoix = () => {
      if (!picked) return;
      picked.innerHTML = '';
      $$('input[type=checkbox]', list).filter(c => c.checked).forEach(c => {
        const b = document.createElement('button'); b.type = 'button'; b.textContent = c.dataset.code + ' ✕'; b.title = 'Retirer';
        b.addEventListener('click', () => { c.checked = false; majChoix(); }); picked.appendChild(b);
      });
    };
    if (q && list) {
      q.addEventListener('input', () => {
        const t = q.value.trim().toLowerCase();
        let vus = 0;
        $$('label', list).forEach(l => { const ok = !t || l.dataset.cherche.includes(t); l.hidden = !ok; if (ok) vus++; });
        $('#aucune-salle').hidden = vus > 0;
      });
      list.addEventListener('change', majChoix);
      majChoix();
    }

    const jour = $('#id_journee_entiere'), h1 = $('#id_heure_debut'), h2 = $('#id_heure_fin');
    const majHeures = () => { if (jour) { h1.disabled = h2.disabled = jour.checked; } };
    if (jour) { jour.addEventListener('change', majHeures); majHeures(); }
    const d1 = $('#id_date_debut'), d2 = $('#id_date_fin');
    if (d1 && d2) d1.addEventListener('change', () => { if (!d2.value || d2.value < d1.value) d2.value = d1.value; });
  }

  // --- Inscription : propose Prénom / NOM d'après prenom.nom@
  const mail = $('#inscription #id_email'), pre = $('#id_first_name'), nom = $('#id_last_name');
  if (mail && pre && nom) {
    const cap = w => w.split('-').map(x => x ? x[0].toLocaleUpperCase('fr') + x.slice(1).toLocaleLowerCase('fr') : x).join('-');
    mail.addEventListener('blur', () => {
      const loc = (mail.value.split('@')[0] || '').replace(/[0-9]+$/, '');
      const parts = loc.split(/[._]/).filter(Boolean);
      if (parts.length >= 2) {
        if (!pre.value) pre.value = cap(parts[0]);
        if (!nom.value) nom.value = parts.slice(1).join(' ').toLocaleUpperCase('fr');
      }
    });
  }

  // --- Écran : horloge et plein écran
  const clk = $('#horloge');
  if (clk) {
    const tic = () => { const d = new Date(); clk.textContent = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
    tic(); setInterval(tic, 15000);
  }
  const fs = $('#plein-ecran');
  if (fs) fs.addEventListener('click', () => { const el = document.documentElement; if (el.requestFullscreen) el.requestFullscreen().catch(() => {}); });

  // --- Confirmations simples
  $$('[data-confirmer]').forEach(f => f.addEventListener('submit', e => { if (!window.confirm(f.dataset.confirmer)) e.preventDefault(); }));
})();
