import random
import string
import time
from collections import defaultdict

# ============================================================
#         G A N   L I K E   N O I S E   G E N E R A T O R
# ============================================================

def gan_noise(base, count=20):
    results = set()
    root = base.lower()

    for _ in range(count):
        latent = [random.randint(-3, 3) for _ in range(random.randint(5, 9))]
        word = []

        for v in latent:
            c = random.choice(root)
            if v < -1:
                c = c.upper()
            if v > 1:
                c = random.choice(string.digits)
            if v == 0:
                c = random.choice("!@#_-.$%")
            word.append(c)

        noisy = "".join(word)
        results.add(noisy)

    return list(results)



# ============================================================
#          P E R S O N A L   I N F O   I N F E R E N C E
# ============================================================

def expand_personal_info(root):
    name_pool = [
        "alex", "sam", "mike", "sara", "lena", "ava", "zoe", "riley",
        "noah", "liam", "mia", "nina", "eric", "kai", "leo"
    ]

    pet_pool = [
        "buddy", "loki", "bella", "max", "rocky", "shadow",
        "zeus", "nova", "ghost", "kira"
    ]

    game_pool = [
        "fortnite", "valorant", "minecraft", "gow", "gtav",
        "cyberpunk", "elden", "halo", "apex"
    ]

    info = {
        "friend": random.choice(name_pool),
        "pet": random.choice(pet_pool),
        "partner": random.choice(name_pool),
        "fav_game": random.choice(game_pool),
        "year": str(random.choice([random.randint(1970,1999), random.randint(2000,2010)])),
        "dob": None
    }

    info["dob"] = info["year"][-2:] + str(random.randint(10,28))

    return info



def personal_info_mutations(root, info):
    results = set()

    fields = [
        info["friend"], info["pet"], info["partner"],
        info["fav_game"], info["year"], info["dob"]
    ]

    for f in fields:
        results.update({
            root + f,
            f + root,
            root + "_" + f,
            f + "_" + root,
            root + f.capitalize(),
            f.capitalize() + root,
        })

    return list(results)

# ============================================================
#                   L E E T S P E A K  M A P
# ============================================================

LEET_MAP = {
    "a": ["4", "@", "a"],
    "e": ["3", "e"],
    "i": ["1", "!", "i"],
    "o": ["0", "o"],
    "s": ["5", "$", "s"],
    "t": ["7", "t"],
    "b": ["8", "b"],
    "g": ["9", "g"],
}


def leetspeak(word):
    """Generate multiple leetspeak variations."""
    results = set([word])
    chars = list(word.lower())

    def transform_all():
        return "".join(random.choice(LEET_MAP.get(c, [c])) for c in chars)

    # Generate several variations
    for _ in range(10):
        results.add(transform_all())

    return list(results)


# ============================================================
#            M A R K O V  C H A I N  G E N E R A T O R
# ============================================================

def build_markov_model(text, n=2):
    model = defaultdict(list)
    for i in range(len(text) - n):
        key = text[i:i + n]
        next_char = text[i + n]
        model[key].append(next_char)
    return model


def markov_generate(model, seed, length=8):
    result = seed
    while len(result) < length:
        key = result[-2:]
        if key in model:
            result += random.choice(model[key])
        else:
            result += random.choice(string.ascii_lowercase)
    return result


def markov_mutations(base):
    """Generate realistic, human-like randomness using Markov logic."""
    training_text = (
        base * 3 +
        "passwordusernameloginsecureaccountadminmastershadowhunterwolfdarknova"
    )

    model = build_markov_model(training_text)

    # Generate several Markov-based strings
    mutations = set()
    for _ in range(15):
        seed = random.choice(base)
        m = markov_generate(model, seed, random.randint(6, 12))
        mutations.add(m)

    return list(mutations)


# ============================================================
#          P O L I C Y - A W A R E  M U T A T I O N S
# ============================================================

def enforce_policy(word):
    """Ensure the word meets typical password rules."""
    has_upper = any(c.isupper() for c in word)
    has_lower = any(c.islower() for c in word)
    has_digit = any(c.isdigit() for c in word)
    has_symbol = any(c in "!@#$%&*_-" for c in word)
    min_len = len(word) >= 8

    if not has_upper and random.random() < 0.7:
        word += random.choice(string.ascii_uppercase)
    if not has_digit:
        word += str(random.randint(0, 9))
    if not has_symbol:
        word += random.choice("!@#$%&*_-")
    if not min_len:
        while len(word) < 8:
            word += random.choice("!@#123")

    return word


def policy_mutations(word):
    """Generate several policy-safe variants."""
    results = []
    for _ in range(10):
        w = word
        w = enforce_policy(w)
        results.append(w)
    return results


# ============================================================
#       C O R E  A I - S T Y L E  I N F E R E N C E
# ============================================================

def maybe(prob=0.5):
    return random.random() < prob


def infer_context(base):
    context = {}

    letters = "".join([c for c in base if c.isalpha()])
    digits = "".join([c for c in base if c.isdigit()])

    context["root"] = letters if letters else base
    context["digits"] = digits if digits else str(random.randint(10, 999))
    context["year"] = digits if (len(digits) == 4) else str(random.randint(1970, 2024))

    context["theme"] = random.choice(
        ["ghost", "wolf", "zero", "dark", "nova", "shadow", "hunter", "void", "hawk"]
    )

    context["nickname"] = random.choice([
        context["root"][:3], context["root"][::-1][:3], "neo", "max", "rio", "kai"
    ])

    return context


# ============================================================
#              C O R E  M U T A T I O N  E N G I N E
# ============================================================

def mutate(base, context):
    variations = set()
    root = context["root"]
    digits = context["digits"]
    year = context["year"]
    nick = context["nickname"]
    theme = context["theme"]

    # Basic forms
    for form in [root, root.lower(), root.upper(), root.capitalize()]:
        variations.add(form)

    # Numeric mixes
    nums = [digits, year, digits[::-1], year[::-1], str(random.randint(10, 999))]
    for n in nums:
        variations.add(root + n)
        variations.add(n + root)

    # Nicknames/themes
    combos = [nick, theme]
    for c in combos:
        variations.add(root + c)
        variations.add(c + root)
        variations.add(root + "_" + c)

    # Symbols
    symbols = "!@#._-$"
    for s in symbols:
        if maybe(0.25):
            variations.add(root + s + digits)

    # Noise randomness
    for _ in range(random.randint(10, 25)):
        noise = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(3, 5)))
        variations.add(root + noise)

    return list(variations)


# ============================================================
#                     M A I N   P R O G R A M
# ============================================================

def generate_ultimate_wordlist():
    print("\n====== Ultimate AI-Driven Wordlist Generator ======\n")

    base = input("Enter a base username/password: ").strip()

    if base == "":
        base = random.choice(["alex99", "shadow101", "novaX", "wolf7"])
        print(f"\nNo input provided → AI generated: {base}")

    # Infer context
    context = infer_context(base)

    print("\nAI inferred context:")
    for k, v in context.items():
        print(f"  {k}: {v}")

    # Generate all mutation layers
    base_set = set()

    # 1. Core mutations
    base_set.update(mutate(base, context))

    # 2. Leetspeak variants
    for w in list(base_set):
        base_set.update(leetspeak(w))

    # 3. Markov chain mutations
    base_set.update(markov_mutations(context["root"]))

    # 4. Policy-safe variants
    for w in list(base_set):
        base_set.update(policy_mutations(w))

    # 5. GAN-like noise
    base_set.update(gan_noise(context["root"], count=30))

    # 6. Personal info inference + mutations
    personal_info = expand_personal_info(context["root"])
    base_set.update(personal_info_mutations(context["root"], personal_info))

    # Shuffle + output
    results = list(base_set)
    random.shuffle(results)

    print(f"\nGenerated {len(results)} dynamic entries:\n")
    for r in results:
        print(r)

    # Save
    filename = f"ultimate_{context['root']}_wordlist.txt"
    with open(filename, "w") as f:
        f.write("\n".join(results))

    print("\nSaved to:", filename)


if __name__ == "__main__":
    generate_ultimate_wordlist()
