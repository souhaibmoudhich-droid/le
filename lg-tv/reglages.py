"""Réglages proposés par `python lgtv.py alleger`, dans l'ordre.

webOS ne laisse aucun outil externe changer ces réglages (sans rooter la TV) :
on les fait à la télécommande, l'outil pose les questions, prend les captures
avant/après et note tout pour que `restaurer.py` sache quoi annuler.

« chemin » : webOS 22 à 25 (menu « Tous les réglages », roue dentée).
« chemin_ancien » : webOS 3.5 à 4.5 (TV 2017-2019, menu Général à icônes à gauche,
où « LG Connect Apps » s'appelle « TV Mobile activée »).
Si une option n'existe pas sur ta TV, réponds n : elle est laissée telle quelle.
"""

REGLAGES = [
    {
        "id": "promotion_accueil",
        "titre": "Pubs sur l'écran d'accueil",
        "pourquoi": "La grande bannière publicitaire et les tuiles sponsorisées de l'accueil LG.",
        "chemin": "Réglages > Général > Système > Paramètres supplémentaires > Paramètres de l'accueil",
        "chemin_ancien": "Réglages > Général > Paramètres d'accueil",
        "action": "Désactive « Promotion de l'accueil » (Home Promotion).",
        "annuler": "Même écran : réactive « Promotion de l'accueil ».",
    },
    {
        "id": "recommandations",
        "titre": "Recommandations de contenu",
        "pourquoi": "Les rangées « À découvrir » poussées par LG et ses partenaires.",
        "chemin": "Réglages > Général > Système > Paramètres supplémentaires > Paramètres de l'accueil",
        "chemin_ancien": "Réglages > Général > Paramètres d'accueil",
        "action": "Désactive « Recommandation de contenu ».",
        "annuler": "Même écran : réactive « Recommandation de contenu ».",
    },
    {
        "id": "pub_ciblee",
        "titre": "Publicité ciblée",
        "pourquoi": "Empêche LG de construire un profil publicitaire à partir de ce que tu regardes.",
        "chemin": "Réglages > Général > Système > Paramètres supplémentaires > Publicité",
        "chemin_ancien": "Réglages > Général > Publicité",
        "action": "Active « Limiter le suivi publicitaire » (et désactive « Publicité personnalisée » s'il existe).",
        "annuler": "Même écran : désactive « Limiter le suivi publicitaire ».",
    },
    {
        "id": "infos_visionnage",
        "titre": "Télémétrie : informations de visionnage",
        "pourquoi": "Envoi à LG de ce que tu regardes et de l'usage des applis.",
        "chemin": "Réglages > Assistance > Confidentialité et conditions > Accords d'utilisation",
        "chemin_ancien": "Réglages > Général > À propos de ce téléviseur > Accords d'utilisateur",
        "action": "Décoche « Informations de visionnage » et « Publicités basées sur l'intérêt », puis « Accepter ». "
                  "Laisse coché « Conditions d'utilisation » (sinon le Content Store et les applis ne marchent plus).",
        "annuler": "Même écran : recoche les cases puis « Accepter ».",
    },
    {
        "id": "live_plus",
        "titre": "Télémétrie : Live Plus (reconnaissance de contenu)",
        "pourquoi": "Analyse l'image à l'écran, même en HDMI, pour savoir ce que tu regardes.",
        "question": "Tu utilises les fonctions interactives des chaînes TV (quiz, votes, infos en direct) ?",
        "chemin": "Réglages > Général > Système > Paramètres supplémentaires",
        "chemin_ancien": "Réglages > Général > Live Plus",
        "action": "Désactive « Live Plus ».",
        "annuler": "Même écran : réactive « Live Plus ».",
    },
    {
        "id": "vocal",
        "titre": "Reconnaissance vocale",
        "pourquoi": "Supprime l'envoi des enregistrements de voix et un service en arrière-plan.",
        "question": "Tu parles à la télécommande (bouton micro) pour chercher ou commander la TV ?",
        "chemin": "Réglages > Assistance > Confidentialité et conditions > Accords d'utilisation",
        "chemin_ancien": "Réglages > Général > À propos de ce téléviseur > Accords d'utilisateur",
        "action": "Décoche « Services de reconnaissance vocale », puis « Accepter ».",
        "annuler": "Même écran : recoche « Services de reconnaissance vocale ».",
    },
    {
        "id": "airplay",
        "titre": "AirPlay / HomeKit",
        "pourquoi": "Un service de moins qui tourne en permanence.",
        "question": "Tu envoies des vidéos ou recopies l'écran depuis un iPhone, un iPad ou un Mac ?",
        "chemin": "Réglages > Général > AirPlay",
        "chemin_ancien": "absent sur les TV d'avant 2019 : réponds n",
        "action": "Désactive « AirPlay ».",
        "annuler": "Même écran : réactive « AirPlay ».",
    },
    {
        "id": "lancement_auto_accueil",
        "titre": "Accueil LG qui s'ouvre au démarrage",
        "pourquoi": "Évite le chargement de l'accueil (et de ses pubs) à chaque allumage.",
        "chemin": "Réglages > Général > Système > Paramètres supplémentaires > Paramètres de l'accueil",
        "chemin_ancien": "Réglages > Général > Paramètres d'accueil",
        "action": "Désactive « Lancement automatique de l'accueil ».",
        "annuler": "Même écran : réactive « Lancement automatique de l'accueil ».",
    },
    {
        "id": "demarrage_rapide",
        "titre": "Démarrage rapide",
        "pourquoi": "La TV s'allume en 2 s au lieu de 15 s ; elle consomme un peu plus en veille (~0,5 W).",
        "question": "Tu préfères la consommation minimale en veille plutôt qu'un allumage rapide ?",
        "chemin": "Réglages > Général > Dispositifs > Paramètres de la TV",
        "chemin_ancien": "Réglages > Général > Démarrage Rapide+",
        "action": "Active « Démarrage rapide+ » (Quick Start+).",
        "annuler": "Même écran : désactive « Démarrage rapide+ ».",
    },
    {
        "id": "lg_channels",
        "titre": "LG Channels (chaînes gratuites avec pubs)",
        "pourquoi": "Chaînes en streaming financées par la pub, qui s'imbriquent dans la liste des chaînes.",
        "question": "Tu regardes les « LG Channels » (chaînes gratuites dans la liste des chaînes) ?",
        "chemin": "Réglages > Chaînes > LG Channels",
        "chemin_ancien": "Réglages > Chaînes > LG Channels (souvent absent : réponds n)",
        "action": "Désactive « LG Channels ».",
        "annuler": "Même écran : réactive « LG Channels ».",
    },
    {
        "id": "ruban_applis",
        "titre": "Applis inutiles du ruban d'accueil",
        "pourquoi": "Rien n'est désinstallé : on déplace en fin de liste celles que tu n'utilises pas.",
        "chemin": "Accueil > ruban des applis > tout à droite « Modifier la liste des applis » (crayon)",
        "chemin_ancien": "Accueil > ruban des applis > « Modifier » (crayon) à droite",
        "action": "Mets en tête : Accueil Zen, 4K Player, Smart IPTV, YouTube, Netflix, Rakuten TV. "
                  "Pousse le reste à la fin. N'utilise jamais « Supprimer ».",
        "annuler": "Même écran : remets l'ordre noté dans sauvegardes/<date>/ruban_accueil.txt.",
    },
    {
        "id": "dns_anti_pub",
        "titre": "Filtre DNS anti-pub (optionnel)",
        "pourquoi": "Bloque les serveurs publicitaires et de télémétrie de LG au niveau du réseau. "
                    "Inconvénient possible : une appli qui refuse de démarrer — il suffit alors de revenir en auto.",
        "question": "Tu préfères ne pas toucher aux réglages réseau de la TV ?",
        "chemin": "Réglages > Général > Réseau > Connexion Wi-Fi > Paramètres Wi-Fi avancés > Modifier",
        "chemin_ancien": "Réglages > Réseau > Connexion Wi-Fi > Paramètres Wi-Fi avancés > Modifier",
        "action": "Décoche « Paramétrage automatique », DNS : 94.140.14.14 (AdGuard DNS, gratuit). "
                  "Note d'abord l'adresse DNS affichée. Puis « Connecter ».",
        "annuler": "Même écran : recoche « Paramétrage automatique » puis « Connecter ».",
    },
]
