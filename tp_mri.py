# //exo 1
# code de l'exo 1
# Fonctionnement : 
# Implémentation du chiffre de César : 
# - Une fonction pour chiffrer un texte en appliquant un décalage sur chaque lettre.
# - Une fonction pour déchiffrer un texte chiffré par César, si le décalage est connu.
# - Une fonction pour tenter tous les décalages possibles et afficher les résultats, 
#   afin d'aider à trouver le bon décalage si inconnu.

# On supposera un alphabet A-Z (lettres majuscules sans accents). 
# Les espaces et caractères non alphabétiques ne seront pas modifiés.
# Le paramètre shift est un entier, positif pour un décalage vers l'avant.

def caesar_encrypt(plaintext, shift):
    res = []
    for c in plaintext:
        if c.isalpha():
            # On travaille en majuscules
            base = 'A' if c.isupper() else 'a'
            offset = (ord(c) - ord(base) + shift) % 26
            res.append(chr(ord(base) + offset))
        else:
            res.append(c)
    return ''.join(res)

def caesar_decrypt(ciphertext, shift):
    # Déchiffrer en faisant un décalage négatif
    return caesar_encrypt(ciphertext, -shift)

def caesar_bruteforce(ciphertext):
    # Essaye tous les décalages de 1 à 25 et print le résultat
    candidates = []
    for s in range(1,26):
        dec = caesar_decrypt(ciphertext, s)
        candidates.append((s, dec))
    return candidates

# //exo 2
# code de l'exo 2
# Le but : 
# Lire un fichier texte contenant un message chiffré par César, tenter de trouver le décalage 
# le plus probable en analysant la fréquence des lettres.
# Méthode simple : le plus fréquent dans un texte chiffré par César correspond souvent au 'E' 
# en français. On pourra donc trouver le décalage en supposant que la lettre la plus fréquente 
# du texte correspond à 'E'.

def letter_frequency_analysis(ciphertext):
    freq = {}
    for c in ciphertext.upper():
        if 'A' <= c <= 'Z':
            freq[c] = freq.get(c, 0) + 1
    if not freq:
        return None
    # Lettre la plus fréquente
    max_letter = max(freq, key=freq.get)
    # On estime que max_letter correspond à 'E' (E=4 indexé à partir de A=0)
    # décalage = position(max_letter) - position(E)
    # position(E)=4, position(A)=0 => ord(max_letter)-ord('A') donne la position
    shift = (ord(max_letter) - ord('E')) % 26
    return shift

def caesar_auto_decrypt_from_file(infilename, outfilename):
    # Lit le fichier, tente de trouver le décalage, déchiffre et écrit dans un autre fichier
    with open(infilename, 'r', encoding='utf-8', errors='ignore') as f:
        ciphertext = f.read()
    found_shift = letter_frequency_analysis(ciphertext)
    if found_shift is None:
        # Si on ne trouve pas de lettre fréquente, on peut tenter bruteforce
        # On prend simplement le premier candidat qui a l'air correct 
        # (Ici, sans heuristique, on se contente du shift 0)
        found_shift = 0
    plaintext = caesar_decrypt(ciphertext, found_shift)
    with open(outfilename, 'w', encoding='utf-8') as f:
        f.write(plaintext)

# //exo 3
# code de l'exo 3
# Le chiffre de Vigenère :
# Formule : C = (P + K) mod 26 
#           P = position de la lettre du texte clair (0=A,...,25=Z)
#           K = position de la lettre de la clé
#           C = position de la lettre chiffrée
# Déchiffrement : P = (C - K) mod 26
# Implémentation :
# - Fonction pour chiffrer avec Vigenère avec une clé donnée.
# - Fonction pour déchiffrer avec Vigenère avec une clé donnée.
# La clé est répétée sur toute la longueur du message.

def vigenere_encrypt(plaintext, key):
    res = []
    key = key.upper()
    key_len = len(key)
    j = 0
    for c in plaintext:
        if c.isalpha():
            base = 'A' if c.isupper() else 'a'
            p = ord(c.upper()) - ord('A')
            k = ord(key[j % key_len]) - ord('A')
            enc = (p + k) % 26
            # On préserve la casse
            res.append(chr(ord(base) + enc))
            j += 1
        else:
            res.append(c)
    return ''.join(res)

def vigenere_decrypt(ciphertext, key):
    res = []
    key = key.upper()
    key_len = len(key)
    j = 0
    for c in ciphertext:
        if c.isalpha():
            base = 'A' if c.isupper() else 'a'
            cpos = ord(c.upper()) - ord('A')
            k = ord(key[j % key_len]) - ord('A')
            dec = (cpos - k) % 26
            res.append(chr(ord(base) + dec))
            j += 1
        else:
            res.append(c)
    return ''.join(res)

# //exo 4
# code de l'exo 4
# Attaque simplifiée de Vigenère lorsque la longueur de la clé est connue :
# Si on connaît la longueur de la clé (par exemple 4), 
# on peut diviser le texte chiffré en 4 sous-suites de caractères (en prenant une lettre sur 4), 
# puis traiter chacune comme un chiffre de César, trouver le décalage avec la technique 
# de fréquence, et reconstituer la clé. 
# Ici on donne juste un exemple de fonction qui, connaissant la longueur de la clé,
# tente de la retrouver.

def guess_vigenere_key(ciphertext, key_length):
    # On suppose que ciphertext est en majuscules (sinon on le convertit)
    ciphertext = ciphertext.upper()
    # Pour chaque position i dans [0, key_length-1], on prend les lettres ciphertext[i::key_length]
    # et on réalise une analyse de fréquence similaire à celle du César.
    guessed_key = []
    for i in range(key_length):
        subseq = ''.join(ciphertext[j] for j in range(i, len(ciphertext), key_length) if 'A'<=ciphertext[j]<='Z')
        if not subseq:
            # Si la sous-séquence est vide, on met A par défaut
            guessed_key.append('A')
            continue
        freq_shift = letter_frequency_analysis(subseq)
        # freq_shift indique le décalage par rapport à E pour aligner max_letter sur E
        # Or, dans Vigenère, ce décalage correspond à la clé. Si C=(P+K) mod 26
        # et max_letter->E => shift = position(max_letter)-position(E)
        # Le K trouvé est juste le shift qui ramène le max_letter sur E.
        # Mais ici on a supposé le shift = (ord(max_letter)-ord('E')) mod 26.
        # Ce shift est en fait la clé à utiliser pour décrypter, donc la lettre de clé est
        # la lettre qui correspond à ce shift (0=A, 1=B, ...).
        if freq_shift is None:
            # sans info, on met A
            guessed_key.append('A')
        else:
            key_letter = chr(ord('A')+freq_shift)
            guessed_key.append(key_letter)
    return ''.join(guessed_key)

# Exemples d'utilisation :
# Pour l'exo 1 :
# plaintext = "HELLO WORLD"
# ciphertext = caesar_encrypt(plaintext, 3)
# print(ciphertext)
# print(caesar_decrypt(ciphertext, 3))
# print(caesar_bruteforce(ciphertext))

# Pour l'exo 2 :
# caesar_auto_decrypt_from_file("chypher2.txt", "decoded.txt")

# Pour l'exo 3 :
# plaintext = "ATTACKATDAWN"
# key = "LEMON"
# enc = vigenere_encrypt(plaintext, key)
# dec = vigenere_decrypt(enc, key)
# print(enc, dec)

# Pour l'exo 4 :
# ciphertext = vigenere_encrypt("CETMESSAGEESTSECRET", "CLEF")
# guessed = guess_vigenere_key(ciphertext, 4)
# print("Clé devinée:", guessed)
