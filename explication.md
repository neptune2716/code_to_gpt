# Documentation de l'application Code to GPT (Project Explorer)

## Introduction

Cette application est un explorateur de projet avancé qui permet de visualiser, explorer et manipuler l'arborescence des fichiers d'un projet. Elle est particulièrement utile pour générer du code qui peut ensuite être envoyé à des modèles comme GPT (d'où le nom "Code to GPT"). L'application permet de sélectionner des fichiers par extension ou manuellement, puis génère une représentation de ces fichiers qui peut être copiée facilement.

## Architecture générale

L'application est construite avec Python et utilise Tkinter pour l'interface graphique, avec des améliorations visuelles via ttkbootstrap. Elle suit une architecture monolithique où la classe principale `ProjectExplorerApp` gère à la fois l'interface utilisateur et la logique métier.

## Composants principaux

1. **Interface utilisateur**: 
   - Une barre de navigation/recherche en haut
   - Un panneau divisé (PanedWindow) contenant:
     - À gauche: l'arborescence du projet
     - À droite: un notebook avec deux onglets (Options et Code généré)
   - Une barre d'état en bas

2. **Gestion des fichiers**:
   - Système de chargement et navigation dans l'arborescence
   - Système de sélection des fichiers (par extension ou manuellement)
   - Système de favoris pour accéder rapidement à des dossiers importants

3. **Génération de code**:
   - Extraction du contenu des fichiers sélectionnés
   - Formatage du texte pour l'envoi à GPT

## Fonctionnalités détaillées

### Navigation dans le projet

- **Sélection du dossier racine**: Via le bouton "Parcourir" ou par drag & drop
- **Navigation hiérarchique**: Double-clic sur un dossier pour y entrer
- **Navigation historique**: Bouton "Retour" pour revenir au dossier précédent
- **Favoris**: Système pour marquer et accéder rapidement à des dossiers importants

### Exploration de l'arborescence

- **Vue arborescente**: Affichage hiérarchique des fichiers et dossiers
- **Icônes**: Différenciation visuelle entre fichiers et dossiers
- **Chargement paresseux**: Chargement des sous-dossiers uniquement à l'ouverture
- **Menu contextuel**: Actions disponibles via clic droit (ouvrir, renommer, etc.)
- **Éléments masqués**: Possibilité de masquer des fichiers/dossiers et de les afficher en gris

### Sélection de fichiers

- **Par extension**: Cochage d'extensions pour sélectionner tous les fichiers correspondants
- **Sélection manuelle**: Ajout/suppression de fichiers individuels via le menu contextuel
- **Liste des fichiers sélectionnés**: Affichage et gestion des fichiers actuellement sélectionnés

### Génération de code

- **Extraction automatique**: Lecture du contenu des fichiers sélectionnés
- **Mise en forme**: Présentation avec séparateurs et chemins de fichiers
- **Copie**: Boutons pour copier l'arborescence, le code, ou les deux

### Recherche

- **Recherche simple**: Par nom de fichier
- **Recherche avancée**: Par nom, extension, date de modification
- **Résultats**: Affichage dans une fenêtre dédiée avec actions disponibles

### Paramètres et personnalisation

- **Thèmes**: Changement entre thème clair et sombre
- **Police**: Choix de la police et de sa taille pour l'affichage du code
- **Extensions reconnues**: Gestion de la liste des extensions considérées comme du texte

## Gestion des données

### Fichiers de configuration

L'application utilise trois fichiers JSON pour stocker ses paramètres:

1. **preferences.json**: Stocke les préférences générales
   - Dernière géométrie de fenêtre
   - Dernier chemin ouvert
   - Extensions sélectionnées
   - Thème actuel
   - Paramètres de police
   - Etc.

2. **favorites.json**: Liste des chemins marqués comme favoris

3. **hidden_items.json**: Liste des chemins masqués dans l'arborescence

### Gestion de l'état

- **selected_files**: Dictionnaire des fichiers actuellement sélectionnés (par extension + manuellement)
- **manual_selected_files**: Dictionnaire des fichiers sélectionnés manuellement uniquement
- **path_to_item**: Mappage des chemins vers les IDs des items dans le Treeview

## Fonctionnalités avancées

### Multithreading

- Chargement de l'arborescence dans un thread séparé pour ne pas bloquer l'interface
- Recherche effectuée dans un thread séparé
- File d'attente (queue) pour communiquer entre les threads et l'interface

### Drag & Drop

- Support du glisser-déposer de dossiers dans l'application

### Debouncing

- System de "debounce" pour la génération de code lors de multiples changements rapides

## Interface utilisateur détaillée

### Zone supérieure
- Champ de chemin avec bouton parcourir
- Bouton retour pour la navigation
- Option pour afficher/masquer les éléments cachés
- Zone de recherche simple

### Panneau gauche (Arborescence)
- Vue hiérarchique du projet
- Chargement paresseux des sous-dossiers
- Icônes différenciées pour fichiers et dossiers
- Support des éléments masqués (affichés en gris)

### Panneau droit (Notebook)
- **Onglet Options**:
  - Sélection des extensions avec bouton "Tout sélectionner/désélectionner"
  - Liste des favoris avec actions associées
  - Liste des fichiers sélectionnés avec possibilité de désélection

- **Onglet Code généré**:
  - Affichage du code extrait des fichiers sélectionnés
  - Boutons pour copier l'arborescence/code/tout

### Barre d'état
- Indicateur de progression
- Messages d'état

## Événements et interactions

- Double-clic sur un dossier: Navigation
- Clic-droit sur un élément: Menu contextuel
- Sélection d'extension: Mise à jour automatique des fichiers sélectionnés et du code
- Changement de chemin: Rechargement de l'arborescence
- Recherche: Exécution en arrière-plan et affichage des résultats

## Fenêtres secondaires

### Paramètres
- Configuration du thème
- Configuration de la police et taille
- Gestion des extensions reconnues

### Résultats de recherche
- Liste des éléments trouvés
- Actions pour ouvrir ou localiser dans l'arborescence

## Conclusion

Cette application est un outil complet pour explorer et extraire du code d'un projet. Elle combine des fonctionnalités d'exploration de fichiers avec des capacités spécifiques pour la sélection et la génération de code à partir de fichiers sources. Sa conception modulaire et ses nombreuses options de personnalisation la rendent adaptée à différents workflows et types de projets.

Pour un rebuild, il serait recommandé de conserver cette architecture générale tout en modernisant potentiellement certains aspects comme la gestion d'état (peut-être avec un pattern MVC plus strict) ou l'interface utilisateur (peut-être avec des composants web via un framework comme PyWebView).