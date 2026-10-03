"""Exploratory global sequence comparison for the LpBgl5/BRENDA near-match.

This checks whether BRENDA's Lactiplantibacillus plantarum WCFS1 F9UU25
sequence is the same accession as LpBgl5 (XOT41254.1); it is not BLAST,
orthology inference, or proof of assay/observation coverage.
"""

from urllib.request import Request, urlopen


SEQUENCES = {
    "LpBgl5_XOT41254.1": (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        "?db=protein&id=XOT41254.1&rettype=fasta&retmode=text"
    ),
    "BRENDA_F9UU25": "https://rest.uniprot.org/uniprotkb/F9UU25.fasta",
}


def fetch_fasta(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Janus-Dataset-research-audit/1.0"})
    with urlopen(request, timeout=30) as response:
        lines = response.read().decode("utf-8").splitlines()
    if not lines or not lines[0].startswith(">"):
        raise ValueError(f"Unexpected FASTA response from {url}")
    return "".join(line.strip() for line in lines[1:])


def needleman_wunsch(a: str, b: str, match: int = 2, mismatch: int = -1, gap: int = -2):
    """Return aligned strings using a basic linear-gap global alignment."""
    n, m = len(a), len(b)
    scores = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        scores[i][0], trace[i][0] = i * gap, 1
    for j in range(1, m + 1):
        scores[0][j], trace[0][j] = j * gap, 2

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            choices = (
                scores[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch),
                scores[i - 1][j] + gap,
                scores[i][j - 1] + gap,
            )
            scores[i][j] = max(choices)
            trace[i][j] = choices.index(scores[i][j])

    i, j = n, m
    aligned_a, aligned_b = [], []
    while i or j:
        direction = trace[i][j]
        if i and j and direction == 0:
            aligned_a.append(a[i - 1])
            aligned_b.append(b[j - 1])
            i -= 1
            j -= 1
        elif i and (j == 0 or direction == 1):
            aligned_a.append(a[i - 1])
            aligned_b.append("-")
            i -= 1
        else:
            aligned_a.append("-")
            aligned_b.append(b[j - 1])
            j -= 1

    return "".join(reversed(aligned_a)), "".join(reversed(aligned_b))


def main() -> None:
    sequences = {name: fetch_fasta(url) for name, url in SEQUENCES.items()}
    a, b = needleman_wunsch(*sequences.values())
    identical = sum(x == y for x, y in zip(a, b))
    paired = sum(x != "-" and y != "-" for x, y in zip(a, b))
    gaps = a.count("-") + b.count("-")

    print("sequence,length")
    for name, sequence in sequences.items():
        print(f"{name},{len(sequence)}")
    print(f"aligned_columns,{len(a)}")
    print(f"identical_residues,{identical}")
    print(f"paired_residue_identity_percent,{100 * identical / paired:.2f}")
    print(f"gap_characters,{gaps}")
    print("Interpretation: exploratory homolog-level similarity only; not exact identity or observation coverage.")


if __name__ == "__main__":
    main()
