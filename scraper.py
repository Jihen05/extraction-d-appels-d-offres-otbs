from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select
import time
import ollama
import json
import requests
from bs4 import BeautifulSoup
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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
PROMPT_EXTRACTION_CDC = """Tu es un système d'extraction de données spécialisé dans les cahiers des charges d'appels d'offres publics tunisiens.

Voici le texte extrait d'un cahier des charges :

---
{texte}
---

Extrais les informations suivantes et retourne UNIQUEMENT un objet JSON valide, sans aucun texte avant ou après, avec exactement ces clés :

{{
  "objet_marche": "",
  "description_technique": "",
  "budget_estime": "",
  "criteres_eligibilite": "",
  "documents_a_fournir": "",
  "criteres_evaluation": "",
  "delai_execution": "",
  "mode_passation": ""
}}

Règles :
- Si une information n'est pas présente dans le texte, laisse la valeur vide "".
- Ne déduis jamais une information qui n'est pas explicitement écrite dans le texte.
- Pour "description_technique", résume en 2-3 phrases maximum ce qui est demandé techniquement.
- Retourne uniquement le JSON, rien d'autre.
"""


def extraire_texte_document(chemin_fichier: str) -> str:
    """Extrait le texte d'un document, quel que soit son format (pdf, docx)."""
    from pipeline import extraire_texte_ocr_structure, convertir_pdf_en_images, extraire_texte_docx
    from PIL import Image

    extension = os.path.splitext(chemin_fichier)[1].lower()

    if extension == ".pdf":
        pages = convertir_pdf_en_images(chemin_fichier)
        return extraire_texte_ocr_structure(pages[0])
    elif extension == ".docx":
        return extraire_texte_docx(chemin_fichier)
    else:
        return ""




def classifier_pertinence(objet_ao: str) -> dict:
    prompt = PROMPT_CLASSIFICATION.format(objet=objet_ao)
    reponse = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    try:
        return json.loads(reponse["message"]["content"])
    except json.JSONDecodeError:
        return {"pertinent": False, "raison": "Erreur de classification"}


def recuperer_lien_document(url_detail: str) -> str:
    try:
        reponse = requests.get(url_detail, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(reponse.text, "html.parser")
        lien = soup.find("a", href=lambda h: h and "/storage/tender/" in h and h.lower().endswith((".pdf", ".docx", ".doc")))
        return lien["href"] if lien else None
    except requests.exceptions.RequestException:
        return None



def telecharger_document(url_doc: str, numero_ao: str, dossier: str = "appels_offres_telecharges") -> str:
    os.makedirs(dossier, exist_ok=True)
    extension = os.path.splitext(url_doc)[1]
    reponse = requests.get(url_doc, timeout=30)
    chemin_fichier = os.path.join(dossier, f"{numero_ao}{extension}")
    with open(chemin_fichier, "wb") as f:
        f.write(reponse.content)
    return chemin_fichier


def extraire_details_page(url_detail: str) -> dict:
    try:
        reponse = requests.get(url_detail, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(reponse.text, "html.parser")
        texte_complet = soup.get_text(separator="\n", strip=True)
        debut = texte_complet.find("Détail de l'appel d'offres")
        fin = texte_complet.find("Avis du cosem", debut)
        texte_utile = texte_complet[debut:fin] if (debut != -1 and fin != -1) else texte_complet
        return {"texte_complet": texte_utile}
    except requests.exceptions.RequestException:
        return {"texte_complet": ""}


def generer_pdf_depuis_details(details: dict, numero_ao: str, dossier: str = "appels_offres_telecharges") -> str:
    os.makedirs(dossier, exist_ok=True)
    chemin_fichier = os.path.join(dossier, f"{numero_ao}_genere.pdf")
    doc = SimpleDocTemplate(chemin_fichier, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Détail de l'appel d'offre {numero_ao}", styles["Title"]), Spacer(1, 12)]
    for ligne in details["texte_complet"].split("\n"):
        ligne = ligne.strip()
        if ligne:
            story.append(Paragraph(ligne, styles["Normal"]))
            story.append(Spacer(1, 4))
    doc.build(story)
    return chemin_fichier


def rechercher_et_filtrer(mot_cle: str) -> list:
    """Fonction principale : recherche, classifie, et télécharge les documents des AO pertinents."""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.maximize_window()

    driver.get("https://www.marchespublics.gov.tn/fr/appels-doffres")
    time.sleep(5)

    premiere_ligne_avant = driver.find_element(By.CSS_SELECTOR, "table tbody tr")

    elements = driver.find_elements(By.NAME, "keywords")
    elements_visibles = [el for el in elements if el.is_displayed()]

    for el in elements_visibles:
        el.click()
        el.send_keys(mot_cle)

    boutons = driver.find_elements(By.CSS_SELECTOR, "button.btn-fill.btn-black.btn-block")
    boutons_visibles = [b for b in boutons if b.is_displayed() and b.text.strip().upper() == "RECHERCHER"]
    bouton_rechercher = boutons_visibles[0] if boutons_visibles else boutons[0]

    driver.execute_script("arguments[0].click();", bouton_rechercher)

    WebDriverWait(driver, 20).until(EC.staleness_of(premiere_ligne_avant))
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tbody tr")) > 0
        and "Traitement en cours" not in d.find_element(By.TAG_NAME, "body").text
    )

    # Sélectionner "100" éléments par page (le maximum disponible)
    menu_affichage = Select(driver.find_element(By.NAME, "data-table_length"))
    menu_affichage.select_by_value("100")

    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "table tbody tr")) > 10
    )
    time.sleep(1)

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

    driver.quit()

    resultats_pertinents = []
    for r in resultats:
        classification = classifier_pertinence(r["objet"])
        if classification["pertinent"]:
            r["raison"] = classification["raison"]
            try:
                lien_doc = recuperer_lien_document(r["url_detail"])
                if lien_doc:
                    r["chemin_document"] = telecharger_document(lien_doc, r["numero_ao"])
                else:
                    details = extraire_details_page(r["url_detail"])
                    r["chemin_document"] = generer_pdf_depuis_details(details, r["numero_ao"])
                resultats_pertinents.append(r)
            except Exception as e:
                print(f"[AVERTISSEMENT] Échec du traitement de {r['numero_ao']} : {e}")
                continue  # passe au résultat suivant sans planter

    return resultats_pertinents