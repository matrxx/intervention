import datetime as dt
import ipaddress
import re

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Bandeau, Intervention, Salle, Site, TypeIntervention, Utilisateur

MDP = "Interventions-2026!"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("initialiser", verbosity=0)
        cls.v = Site.objects.get(code="versailles")
        cls.agent = Utilisateur.objects.create_user("marie.dupont@culture.gouv.fr", MDP, first_name="Marie", last_name="DUPONT")
        cls.autre = Utilisateur.objects.create_user("paul.martin@culture.gouv.fr", MDP, first_name="Paul", last_name="MARTIN")
        cls.admin = Utilisateur.objects.create_user("admin.test@culture.gouv.fr", MDP, first_name="Admin", last_name="TEST", is_staff=True)

    def connecter(self, u, site="versailles"):
        s = Site.objects.get(code=site)
        return self.client.post(reverse("planning:connexion"), {"site": s.pk, "email": u.email, "password": MDP})


class InitialisationTests(Base):
    def test_donnees_de_reference(self):
        self.assertEqual(Salle.objects.filter(site=self.v).count(), 116)
        self.assertEqual(TypeIntervention.objects.count(), 9)
        self.assertTrue(Site.objects.filter(code="louvre").exists())


class ComptesTests(Base):
    def test_inscription_refuse_domaine_externe(self):
        r = self.client.post(reverse("planning:inscription"), {"email": "x@gmail.com", "first_name": "A", "last_name": "B",
                                                               "password1": MDP, "password2": MDP})
        self.assertContains(r, "peuvent créer un compte")
        self.assertFalse(Utilisateur.objects.filter(email="x@gmail.com").exists())

    def test_inscription_puis_activation(self):
        r = self.client.post(reverse("planning:inscription"), {"email": "Jean.Petit@culture.gouv.fr", "first_name": "Jean",
                                                               "last_name": "Petit", "password1": MDP, "password2": MDP})
        self.assertContains(r, "Vérifiez votre messagerie")
        u = Utilisateur.objects.get(email="jean.petit@culture.gouv.fr")
        self.assertFalse(u.is_active)
        self.assertEqual(u.last_name, "PETIT")
        self.assertEqual(len(mail.outbox), 1)
        lien = re.search(r"https?://[^\s]+/activation/[^\s]+", mail.outbox[0].body).group(0)
        # connexion impossible avant activation
        self.assertContains(self.connecter(u), "pas encore activé")
        self.client.get(lien.replace("http://testserver", ""))
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        # lien à usage unique
        self.client.get(lien.replace("http://testserver", ""))
        self.assertRedirects(self.connecter(u), reverse("planning:semaine", args=["versailles"]))

    def test_mot_de_passe_trop_court(self):
        r = self.client.post(reverse("planning:inscription"), {"email": "a.b@culture.gouv.fr", "first_name": "A", "last_name": "B",
                                                               "password1": "court", "password2": "court"})
        self.assertContains(r, "12 caractères")

    @override_settings(CONNEXION_ESSAIS_MAX=3)
    def test_blocage_apres_echecs(self):
        for _ in range(3):
            self.client.post(reverse("planning:connexion"), {"site": self.v.pk, "email": self.agent.email, "password": "faux"})
        self.agent.refresh_from_db()
        self.assertIsNotNone(self.agent.bloque_jusqua)
        self.assertContains(self.connecter(self.agent), "essais infructueux : réessayez")

    def test_reinitialisation_envoie_un_mail(self):
        self.client.post(reverse("planning:reinit"), {"email": self.agent.email})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/mot-de-passe/", mail.outbox[0].body)


class InterventionTests(Base):
    def setUp(self):
        self.connecter(self.agent)
        self.lundi = timezone.localdate() - dt.timedelta(days=timezone.localdate().weekday())
        self.maint = TypeIntervention.objects.get(code="maintenance")

    def donnees(self, **kw):
        d = {"type": self.maint.pk, "description": "Contrôle CTA", "portee": "salles",
             "salles": [Salle.objects.get(code="G205").pk], "date_debut": self.lundi, "date_fin": self.lundi + dt.timedelta(days=2),
             "heure_debut": "09:00", "heure_fin": "12:00", "proxyclick": "on"}
        d.update(kw)
        return d

    def test_creation_hote_automatique(self):
        r = self.client.post(reverse("planning:nouvelle", args=["versailles"]), self.donnees())
        self.assertEqual(r.status_code, 302)
        iv = Intervention.objects.get()
        self.assertEqual(iv.hote, "Marie DUPONT")
        self.assertEqual(iv.cree_par, self.agent)
        page = self.client.get(reverse("planning:semaine", args=["versailles"]) + f"?d={self.lundi}")
        self.assertContains(page, "Contrôle CTA")
        self.assertContains(page, "Sur plusieurs jours")

    def test_validations(self):
        r = self.client.post(reverse("planning:nouvelle", args=["versailles"]), self.donnees(salles=[], date_fin=self.lundi - dt.timedelta(days=1)))
        self.assertContains(r, "au moins une salle")
        self.assertContains(r, "date de fin est avant")
        self.assertFalse(Intervention.objects.exists())

    def test_portee_niveau(self):
        zone_h = self.v.zones.get(code="H")
        r = self.client.post(reverse("planning:nouvelle", args=["versailles"]),
                             self.donnees(portee="niveau", zone=zone_h.pk, niveau="2e étage", salles=[], journee_entiere="on"))
        self.assertEqual(r.status_code, 302)
        iv = Intervention.objects.get()
        self.assertEqual(iv.lieu(), "Aile H · 2e étage")
        self.assertIsNone(iv.heure_debut)

    def test_droits_de_modification(self):
        self.client.post(reverse("planning:nouvelle", args=["versailles"]), self.donnees())
        iv = Intervention.objects.get()
        self.client.post(reverse("planning:deconnexion"))
        self.connecter(self.autre)
        self.assertEqual(self.client.get(reverse("planning:modifier", args=["versailles", iv.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("planning:supprimer", args=["versailles", iv.pk])).status_code, 403)
        self.client.post(reverse("planning:deconnexion"))
        self.connecter(self.admin)
        self.client.post(reverse("planning:supprimer", args=["versailles", iv.pk]))
        self.assertFalse(Intervention.objects.exists())

    def test_ecran_sans_compte_et_bandeau(self):
        self.client.post(reverse("planning:nouvelle", args=["versailles"]), self.donnees())
        Bandeau.objects.create(genre="fermeture", texte="réouverture lundi", date_debut=timezone.localdate(), date_fin=timezone.localdate())
        self.client.post(reverse("planning:deconnexion"))
        r = self.client.get(reverse("planning:ecran", args=["versailles"]))
        self.assertContains(r, "Contrôle CTA")
        self.assertContains(r, "Fermeture du site — réouverture lundi")
        self.assertContains(r, "✓ Proxyclick")
        self.assertNotContains(r, "✓ Plan de prévention")

    def test_semaine_exige_connexion(self):
        self.client.post(reverse("planning:deconnexion"))
        r = self.client.get(reverse("planning:semaine", args=["versailles"]))
        self.assertEqual(r.status_code, 302)


class FiltrageIPTests(Base):
    @override_settings(RESEAUX_AUTORISES=[ipaddress.ip_network("10.10.0.0/16")])
    def test_refus_hors_plage(self):
        r = self.client.get(reverse("planning:connexion"), REMOTE_ADDR="192.168.1.20")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "192.168.1.20", status_code=403)
        self.assertEqual(self.client.get(reverse("planning:connexion"), REMOTE_ADDR="10.10.4.2").status_code, 200)

    @override_settings(RESEAUX_AUTORISES=[ipaddress.ip_network("10.10.0.0/16")],
                       PROXYS_DE_CONFIANCE=[ipaddress.ip_network("172.31.250.0/24")])
    def test_derriere_nginx(self):
        ok = self.client.get(reverse("planning:connexion"), REMOTE_ADDR="172.31.250.10", HTTP_X_FORWARDED_FOR="10.10.4.2")
        self.assertEqual(ok.status_code, 200)
        ko = self.client.get(reverse("planning:connexion"), REMOTE_ADDR="172.31.250.10", HTTP_X_FORWARDED_FOR="10.10.4.2, 192.168.1.20")
        self.assertEqual(ko.status_code, 403)
        # un poste qui n'est pas le proxy ne peut pas usurper une adresse autorisée
        usurpe = self.client.get(reverse("planning:connexion"), REMOTE_ADDR="192.168.1.20", HTTP_X_FORWARDED_FOR="10.10.4.2")
        self.assertEqual(usurpe.status_code, 403)

    @override_settings(RESEAUX_AUTORISES=[ipaddress.ip_network("10.10.0.0/16")])
    def test_sante_toujours_accessible(self):
        self.assertEqual(self.client.get("/sante/", REMOTE_ADDR="192.168.1.20").status_code, 200)


class ImportTests(Base):
    def setUp(self):
        self.connecter(self.admin)
        self.url = reverse("planning:import_salles", args=["versailles"])

    def deposer(self, contenu, mode="maj", enc="utf-8-sig"):
        f = SimpleUploadedFile("locaux.csv", contenu.encode(enc), content_type="text/csv")
        return self.client.post(self.url, {"fichier": f, "mode": mode})

    def test_apercu_puis_import_deux_sites(self):
        csv = ("site;zone;zone_nom;niveau;ordre_niveau;code;libelle;active\n"
               "versailles;G;avenue de Paris;RDC;0;G002A;Atelier dorure (modifié);oui\n"
               "louvre;FL;Pavillon de Flore;Sous-sol;;FL001;Laboratoire;oui\n")
        r = self.deposer(csv)
        self.assertContains(r, "Confirmer l'import")
        self.assertEqual(Salle.objects.get(code="G002A").libelle, "Atelier Dorure")  # rien n'a changé à l'aperçu
        self.client.post(self.url, {"confirmer": "1"})
        self.assertEqual(Salle.objects.get(code="G002A").libelle, "Atelier dorure (modifié)")
        fl = Salle.objects.get(code="FL001")
        self.assertEqual(fl.site.code, "louvre")
        self.assertEqual(fl.ordre_niveau, -1)
        self.assertEqual(Salle.objects.filter(site=self.v, active=True).count(), 116)

    def test_mode_remplacer_desactive(self):
        csv = "site;zone;niveau;code;libelle\nversailles;G;RDC;G002A;Atelier\n"
        self.deposer(csv, mode="remplacer")
        self.client.post(self.url, {"confirmer": "1"})
        self.assertEqual(Salle.objects.filter(site=self.v, active=True).count(), 1)
        self.assertEqual(Salle.objects.filter(site=self.v).count(), 116)

    def test_erreurs_signalees(self):
        csv = "site;zone;niveau;code\nversailles;G;RDC;X1\nversailles;G;RDC;X1\ninconnu;A;RDC;Z9\nversailles;;RDC;X2\n"
        r = self.deposer(csv)
        self.assertContains(r, "apparaît déjà ligne 2")
        self.assertContains(r, "inconnu")
        self.assertContains(r, "« zone » est vide")
        self.assertNotContains(r, "Confirmer l'import")

    def test_excel_windows_cp1252_et_virgules(self):
        csv = "site,zone,niveau,code,libelle\nversailles,H,2e étage,H299,Réserve test\n"
        self.deposer(csv, enc="cp1252")
        self.client.post(self.url, {"confirmer": "1"})
        self.assertEqual(Salle.objects.get(code="H299").libelle, "Réserve test")

    def test_export_reimportable(self):
        r = self.client.get(reverse("planning:export_salles") + "?site=versailles")
        texte = r.content.decode("utf-8-sig")
        self.assertTrue(texte.startswith("site;zone;zone_nom;niveau"))
        self.assertEqual(len(texte.strip().splitlines()), 117)

    def test_reserve_aux_admins(self):
        self.client.post(reverse("planning:deconnexion"))
        self.connecter(self.agent)
        self.assertEqual(self.client.get(self.url).status_code, 403)
