import ollama
import json

PROMPT_EXTRACTION = """Tu es un système d'extraction de données spécialisé dans les offres commerciales (achat ou vente de matériel).

Voici le texte brut extrait par OCR d'une offre commerciale :

---
{texte_ocr}
---

Extrais les informations suivantes et retourne UNIQUEMENT un objet JSON valide, sans aucun texte avant ou après, avec exactement ces clés :

{{
  "numero_offre": "",
  "date": "",
  "client": "",
  "fournisseur": "",
  "type": "",
  "reference_article": "",
  "designation": "",
  "quantite": "",
  "prix_unitaire": "",
  "prix_total": "",
  "devise": "",
  "delai_livraison": "",
  "conditions_paiement": "",
  "incoterm": "",
  "validite_offre": "",
  "coordonnees": ""
}}

Règles :
- Si une information n'est pas présente dans le texte, laisse la valeur vide "".
- Ne déduis jamais une information qui n'est pas explicitement écrite dans le texte.
- Le champ "type" doit valoir "achat" ou "vente" si déductible, sinon laisse vide.
- Retourne uniquement le JSON, rien d'autre.
"""

texte_ocr = """Offre N° 2026-0587
Date : 04/08/2026
Client : Société ABC
Fournisseur : OneTech Business Solutions
Référence article : REF-1234
Désignation : Vanne hydraulique 3 pouces
Quantité : 50
Prix unitaire : 120 TND
Prix total : 6000 TND
Délai de livraison ; 15 jours"""

prompt = PROMPT_EXTRACTION.format(texte_ocr=texte_ocr)

reponse = ollama.chat(
    model="mistral",
    messages=[{"role": "user", "content": prompt}]
)

contenu = reponse["message"]["content"]
print("Réponse brute du modèle :")
print(contenu)

import os
from datetime import datetime

try:
    donnees = json.loads(contenu)
    print("\n✅ JSON valide, données extraites :")
    print(json.dumps(donnees, indent=2, ensure_ascii=False))

    # Créer un dossier de sortie s'il n'existe pas encore
    dossier_sortie = "resultats"
    os.makedirs(dossier_sortie, exist_ok=True)

    # Construire un nom de fichier basé sur le numéro d'offre (ou un horodatage si absent)
    numero = donnees.get("numero_offre", "").strip()
    if numero:
        nom_fichier = f"offre_{numero}.json"
    else:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_fichier = f"offre_{horodatage}.json"

    chemin_fichier = os.path.join(dossier_sortie, nom_fichier)

    # Sauvegarder le JSON dans le fichier
    with open(chemin_fichier, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Fichier sauvegardé : {chemin_fichier}")

except json.JSONDecodeError as e:
    print(f"\n❌ Erreur de parsing JSON : {e}")