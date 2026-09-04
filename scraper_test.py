from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import ollama         
import json
import requests           
from bs4 import BeautifulSoup   
import os  
from pipeline import traiter_offre_interface

PROMPT_CLASSIFICATION = """Tu es un assistant qui aide une entreprise tunisienne de services IT/Télécom (OneTech Business Solutions) à identifier les appels d'offres publics pertinents pour son activité.

Les domaines d'activité de l'entreprise sont :
- Sécurité informatique et cybersécurité
- Communications unifiées et collaboration
- Data Center et systèmes serveurs
- Infrastructure réseau (networking)
- Gestion et exploitation IT
- Solutions de conformité financière

Voici l'objet d'un appel d'offre public tunisien :
"{objet}"

Cet appel d'offre correspond-il à l'un des domaines d'activité de l'entreprise ?

Réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après, avec cette structure exacte :
{{
  "pertinent": true ou false,
  "raison": "courte justification en une phrase"
}}
"""


def classifier_pertinence(objet_ao: str) -> dict:
    """Détermine si un appel d'offre est pertinent pour l'activité d'OneTech."""
    prompt = PROMPT_CLASSIFICATION.format(objet=objet_ao)

    reponse = ollama.chat(
        model="mistral",
        messages=[{"role": "user", "content": prompt}]
    )

    contenu = reponse["message"]["content"]

    try:
        return json.loads(contenu)
    except json.JSONDecodeError:
        return {"pertinent": False, "raison": "Erreur de classification"}
def recuperer_lien_document(url_detail: str) -> str:
    """Visite la page de détail d'un AO et récupère le lien du document (PDF ou Word)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    reponse = requests.get(url_detail, headers=headers, timeout=15)
    soup = BeautifulSoup(reponse.text, "html.parser")

    # Chercher un lien vers un document (pdf, docx, doc) dans le dossier "storage/tender"
    lien = soup.find("a", href=lambda h: h and "/storage/tender/" in h and h.lower().endswith((".pdf", ".docx", ".doc")))

    if lien:
        return lien["href"]
    return None

def telecharger_document(url_doc: str, numero_ao: str, dossier: str = "appels_offres_telecharges") -> str:
    """Télécharge le document (PDF ou Word) d'un appel d'offre, en gardant sa vraie extension."""
    os.makedirs(dossier, exist_ok=True)
    extension = os.path.splitext(url_doc)[1]  # .pdf ou .docx
    reponse = requests.get(url_doc, timeout=30)
    chemin_fichier = os.path.join(dossier, f"{numero_ao}{extension}")
    with open(chemin_fichier, "wb") as f:
        f.write(reponse.content)
    return chemin_fichier


def extraire_details_page(url_detail: str) -> dict:
    """Extrait le texte de la section 'Détail de l'appel d'offres', entre le titre et le footer."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    reponse = requests.get(url_detail, headers=headers, timeout=15)
    soup = BeautifulSoup(reponse.text, "html.parser")

    texte_complet = soup.get_text(separator="\n", strip=True)

    debut = texte_complet.find("Détail de l'appel d'offres")
    fin = texte_complet.find("Avis du cosem", debut)

    if debut != -1 and fin != -1:
        texte_utile = texte_complet[debut:fin]
    else:
        texte_utile = texte_complet  # secours si les marqueurs ne sont pas trouvés

    return {"texte_complet": texte_utile}
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
def extraire_details_page(url_detail: str) -> dict:
    """Extrait le contenu textuel de la section principale de la page de détail d'un AO."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    reponse = requests.get(url_detail, headers=headers, timeout=15)
    soup = BeautifulSoup(reponse.text, "html.parser")

    conteneurs = soup.find_all("div", class_="container")
    meilleur_conteneur = max(conteneurs, key=lambda c: len(c.get_text(strip=True)))
    texte_brut = meilleur_conteneur.get_text(separator="\n", strip=True)

    return {"texte_complet": texte_brut}

def generer_pdf_depuis_details(details: dict, numero_ao: str, dossier: str = "appels_offres_telecharges") -> str:
    """Génère un PDF à partir du texte extrait de la page de détail (quand aucun PDF officiel n'existe)."""
    os.makedirs(dossier, exist_ok=True)
    chemin_fichier = os.path.join(dossier, f"{numero_ao}_genere.pdf")

    doc = SimpleDocTemplate(chemin_fichier, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Détail de l'appel d'offre {numero_ao}", styles["Title"]))
    story.append(Spacer(1, 12))

    # Découper le texte en paragraphes (une ligne = un paragraphe, pour rester lisible)
    for ligne in details["texte_complet"].split("\n"):
        ligne = ligne.strip()
        if ligne:
            story.append(Paragraph(ligne, styles["Normal"]))
            story.append(Spacer(1, 4))

    doc.build(story)
    return chemin_fichier
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)
driver.maximize_window()

driver.get("https://www.marchespublics.gov.tn/fr/appels-doffres")
time.sleep(5)

premiere_ligne_avant = driver.find_element(By.CSS_SELECTOR, "table tbody tr")

elements = driver.find_elements(By.NAME, "keywords")
elements_visibles = [el for el in elements if el.is_displayed()]
champ_recherche = max(elements_visibles, key=lambda el: el.location['y'])

champ_recherche.click()
champ_recherche.send_keys("informatique")

bouton_rechercher = driver.find_element(By.CLASS_NAME, "recherche-btn")
bouton_rechercher.click()

print("Recherche lancée, attente du changement de résultats...")

# Étape 1 : attendre que l'ancienne ligne disparaisse
WebDriverWait(driver, 20).until(EC.staleness_of(premiere_ligne_avant))
print("Ancien contenu disparu, attente du nouveau contenu...")

# Étape 2 : attendre que le message "Traitement en cours" disparaisse ET que de vraies lignes soient là
WebDriverWait(driver, 20).until(
    lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tbody tr")) > 0
    and "Traitement en cours" not in d.find_element(By.TAG_NAME, "body").text
)

print("Résultats finaux chargés avec succès.")

driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
time.sleep(1)

driver.save_screenshot("debug_resultats.png")
print("Capture d'écran enregistrée : debug_resultats.png")

time.sleep(10)
# Extraire les données de chaque ligne du tableau, avec l'URL du détail
lignes = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

resultats = []
for ligne in lignes:
    cellules = ligne.find_elements(By.TAG_NAME, "td")
    if len(cellules) >= 5:
        numero_ao = cellules[0].text.strip()
        resultats.append({
            "numero_ao": numero_ao,
            "acheteur_public": cellules[1].text.strip(),
            "objet": cellules[2].text.strip(),
            "date_limite": cellules[3].text.strip(),
            "date_publication": cellules[4].text.strip(),
            "url_detail": f"https://www.marchespublics.gov.tn/fr/appels-doffres/{numero_ao}"
        })

print(f"\n{len(resultats)} résultats extraits de cette page :\n")
for r in resultats:
    print(r)
driver.quit()
print("\n--- Classification et téléchargement des AO pertinents ---\n")

for r in resultats:
    classification = classifier_pertinence(r["objet"])
    r["pertinent"] = classification["pertinent"]
    r["raison"] = classification["raison"]
    statut = "✅ PERTINENT" if classification["pertinent"] else "❌ non pertinent"
    print(f"{statut} — {r['numero_ao']} : {r['objet'][:60]}...")
    print(f"   Raison : {classification['raison']}")

    if classification["pertinent"]:
        lien_doc = recuperer_lien_document(r["url_detail"])
        if lien_doc:
            chemin = telecharger_document(lien_doc, r["numero_ao"])
            print(f"   📥 Document officiel téléchargé : {chemin}")
        else:
            details = extraire_details_page(r["url_detail"])
            chemin = generer_pdf_depuis_details(details, r["numero_ao"])
            print(f"   📄 Aucun document officiel — PDF généré : {chemin}")
    print()
print("\n--- Traitement des documents téléchargés avec le pipeline d'extraction ---\n")

dossier_telecharges = "appels_offres_telecharges"
for nom_fichier in os.listdir(dossier_telecharges):
    chemin_complet = os.path.join(dossier_telecharges, nom_fichier)
    print(f"📄 Traitement de : {nom_fichier}")

    texte_ocr, donnees = traiter_offre_interface(chemin_complet)

    if donnees:
        print(f"   ✅ Extraction réussie : {donnees.get('numero_offre', 'N/A')}")
    else:
        print(f"   ⚠️ Échec de l'extraction pour {nom_fichier}")
    print()