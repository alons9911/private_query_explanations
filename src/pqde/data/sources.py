"""Raw dataset acquisition: download (or generate) and normalise the four datasets.

=============  =========================================================  ==========
dataset        source                                                     N
=============  =========================================================  ==========
adult          UCI Adult census extract (train+test, 48,842 rows)         48,842
tax            Tax benchmark of the data-cleaning literature (BigDaMa /    200,000
               raha copy of the generator output, clean version);
               optionally up-sampled to the 500,000 rows of the paper
stackoverflow  Stack Overflow Developer Survey (2024).  The official       ~65,000
               download host is not always reachable; if the file is
               absent a *synthetic* generator with the same normalised
               schema is used and the dataset is flagged ``synthetic``
hospital       HoloClean hospital benchmark (dirty version, 1,000 rows),   1,000
               which violates HospitalName->ZipCode,
               HospitalName->PhoneNumber and ZipCode->City
=============  =========================================================  ==========

All loaders return a ``pandas.DataFrame`` with the attribute names used in
the paper (``hoursPerWeek``, ``gender``, ``MaritalStatus``, ``HasChild``,
``WorkRemote``, ``UsingAI``, ``HospitalType`` ...) and a ``meta`` dict.
"""

from __future__ import annotations

import hashlib
import io
import os
import urllib.request
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DIR = Path(os.environ.get("PQDE_DATA_DIR", REPO_ROOT / "data" / "raw"))

URLS = {
    "adult": [
        "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data",
        "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test",
    ],
    # mirror with train+test concatenated (48,842 rows, no header)
    "adult_mirror": ["https://raw.githubusercontent.com/jbrownlee/Datasets/master/adult-all.csv"],
    "tax": ["https://raw.githubusercontent.com/BigDaMa/raha/master/datasets/tax/clean.csv"],
    # the same 200k tuples with injected errors (typos, flipped flags, wrong exemptions)
    "tax_dirty": ["https://raw.githubusercontent.com/BigDaMa/raha/master/datasets/tax/dirty.csv"],
    "hospital": ["https://raw.githubusercontent.com/HoloClean/holoclean/master/testdata/hospital.csv"],
    # ground truth in (tid, attribute, correct_val) form; used only to read the declared value domains
    "hospital_clean": ["https://raw.githubusercontent.com/HoloClean/holoclean/master/testdata/hospital_clean.csv"],
    "stackoverflow": ["https://survey.stackoverflow.co/datasets/stack-overflow-developer-survey-2024.zip"],
    # IPUMS-CPS extract and codebook distributed with DPXPlain (Tao et al., PVLDB 16(1), 2022)
    "ipums": ["https://raw.githubusercontent.com/yuchaotao/Private-Explanation-System/main/data/ipums/cps_00005.csv.gz",
              "https://raw.githubusercontent.com/yuchaotao/Private-Explanation-System/main/data/ipums/cps_00005.xml"],
}

ADULT_COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "educationNum", "maritalStatus", "occupation",
    "relationship", "race", "gender", "capitalGain", "capitalLoss", "hoursPerWeek", "nativeCountry",
    "income",
]


def _download(url: str, dest: Path, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "pqde-reproduction/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, raw_dir: Path | None = None, force: bool = False) -> dict:
    """Download the raw files of ``name`` into ``raw_dir`` (idempotent).

    Returns a dict describing what is on disk.  Download failures are reported,
    not raised, so that a partially reachable network still yields what it can.
    """
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    out: dict = {"dataset": name, "files": {}, "errors": []}
    if name == "adult":
        d = raw_dir / "adult"
        target = d / "adult-all.csv"
        if target.exists() and not force:
            out["files"]["adult-all.csv"] = sha256(target)
            return out
        try:  # official UCI files first
            parts = []
            for url in URLS["adult"]:
                p = _download(url, d / Path(url).name)
                parts.append(p)
            frames = []
            for p in parts:
                df = pd.read_csv(p, header=None, skipinitialspace=True, comment="|")
                frames.append(df)
            pd.concat(frames).to_csv(target, header=False, index=False)
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"UCI: {e}")
            try:
                _download(URLS["adult_mirror"][0], target)
            except Exception as e2:  # noqa: BLE001
                out["errors"].append(f"mirror: {e2}")
        if target.exists():
            out["files"]["adult-all.csv"] = sha256(target)
    elif name in ("tax", "tax_dirty", "hospital"):
        d = raw_dir / ("tax" if name == "tax_dirty" else name)
        targets = [(URLS["tax"][0], d / "tax_clean.csv")] if name == "tax" else [
            (URLS["tax"][0], d / "tax_clean.csv"), (URLS["tax_dirty"][0], d / "tax_dirty.csv")] if name == "tax_dirty" else [
            (URLS["hospital"][0], d / "hospital.csv"), (URLS["hospital_clean"][0], d / "hospital_clean.csv")]
        for url, target in targets:
            if not target.exists() or force:
                try:
                    _download(url, target)
                except Exception as e:  # noqa: BLE001
                    out["errors"].append(f"{target.name}: {e}")
            if target.exists():
                out["files"][target.name] = sha256(target)
    elif name == "ipums":
        d = raw_dir / "ipums"
        for url in URLS["ipums"]:
            target = d / Path(url).name
            if not target.exists() or force:
                try:
                    _download(url, target, timeout=600)
                except Exception as e:  # noqa: BLE001
                    out["errors"].append(f"{target.name}: {e}")
            if target.exists():
                out["files"][target.name] = sha256(target)
    elif name == "stackoverflow":
        d = raw_dir / "stackoverflow"
        target = d / "survey_results_public.csv"
        if not target.exists() or force:
            try:
                z = _download(URLS[name][0], d / "survey.zip")
                with zipfile.ZipFile(z) as zf:
                    member = next(m for m in zf.namelist() if m.endswith("survey_results_public.csv"))
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
            except Exception as e:  # noqa: BLE001
                out["errors"].append(
                    f"{e} -- place survey_results_public.csv in {d} manually, otherwise the synthetic "
                    "generator is used"
                )
        if target.exists():
            out["files"][target.name] = sha256(target)
    else:
        raise KeyError(f"unknown dataset {name!r}")
    return out


# --------------------------------------------------------------------------- Adult


def load_adult(raw_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    path = raw_dir / "adult" / "adult-all.csv"
    if not path.exists():
        fetch("adult", raw_dir)
    df = pd.read_csv(path, header=None, names=ADULT_COLUMNS, skipinitialspace=True, na_values=["?"])
    df = df.dropna(subset=["age"])  # guards against a trailing blank line
    df["income"] = df["income"].astype(str).str.strip().str.rstrip(".").map({">50K": 1, "<=50K": 0}).astype(int)
    for c in ["age", "hoursPerWeek", "educationNum", "capitalGain", "capitalLoss", "fnlwgt"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["workclass", "education", "maritalStatus", "occupation", "relationship", "race", "gender", "nativeCountry"]:
        df[c] = df[c].astype("string").str.strip()
    return df.reset_index(drop=True), {"source": str(path), "synthetic": False}


# --------------------------------------------------------------------------- Tax

TAX_RENAME = {
    "f_name": "FName", "l_name": "LName", "gender": "Gender", "area_code": "AreaCode", "phone": "Phone",
    "city": "City", "state": "State", "zip": "Zip", "marital_status": "MaritalStatus",
    "has_child": "HasChild", "salary": "Salary", "rate": "Rate", "single_exemp": "SingleExemp",
    "married_exemp": "MarriedExemp", "child_exemp": "ChildExemp",
}


def load_tax(raw_dir: Path | None = None, target_rows: int | None = None, seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """The tax benchmark.  ``target_rows`` > file size up-samples rows with replacement."""
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    path = raw_dir / "tax" / "tax_clean.csv"
    if not path.exists():
        fetch("tax", raw_dir)
    df = pd.read_csv(path, dtype=str).rename(columns=TAX_RENAME)
    for c in ["Salary", "Rate", "SingleExemp", "MarriedExemp", "ChildExemp"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    meta = {"source": str(path), "synthetic": False, "file_rows": len(df)}
    if target_rows and target_rows != len(df):
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(df), size=target_rows, replace=target_rows > len(df))
        df = df.iloc[np.sort(idx)].reset_index(drop=True)
        meta["resampled_to"] = target_rows
        meta["resample_seed"] = seed
    return df, meta


def load_tax_dirty(raw_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """The dirty tax relation, for consistent query answering.

    Pure formatting differences of the dirty file (``'01907'`` vs ``'1907'``,
    ``'7.0'`` vs ``'7'``) are normalised so that only the injected errors remain
    (typos in City/State, flipped MaritalStatus/HasChild, wrong exemptions).
    ``meta["declared_domains"]`` holds the categorical domains of the clean file.
    """
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    path = raw_dir / "tax" / "tax_dirty.csv"
    clean = raw_dir / "tax" / "tax_clean.csv"
    if not path.exists() or not clean.exists():
        fetch("tax_dirty", raw_dir)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""]).rename(columns=TAX_RENAME)
    df["Zip"] = df["Zip"].str.lstrip("0")
    for c in ["Salary", "Rate", "SingleExemp", "MarriedExemp", "ChildExemp"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    meta = {"source": str(path), "synthetic": False}
    if clean.exists():
        cl = pd.read_csv(clean, dtype=str, keep_default_na=False, na_values=[""]).rename(columns=TAX_RENAME)
        meta["declared_domains"] = {a: sorted(cl[a].dropna().unique().tolist())
                                    for a in ["Gender", "State", "MaritalStatus", "HasChild"]}
    return df, meta


# --------------------------------------------------------------------------- Hospital


def load_hospital(raw_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """The dirty hospital relation.

    ``meta["declared_domains"]`` holds, per attribute, the values of the clean
    ground truth: they play the role of the domain declared by the schema
    (Section 2.1), so typo values such as ``'yxs'`` fall outside it.
    """
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    path = raw_dir / "hospital" / "hospital.csv"
    clean = raw_dir / "hospital" / "hospital_clean.csv"
    if not path.exists() or not clean.exists():
        fetch("hospital", raw_dir)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df["Score"] = pd.to_numeric(df["Score"].str.rstrip("%"), errors="coerce")
    df["Sample"] = pd.to_numeric(df["Sample"].str.extract(r"(\d+)")[0], errors="coerce")
    meta = {"source": str(path), "synthetic": False}
    if clean.exists():
        gt = pd.read_csv(clean, dtype=str, keep_default_na=False, na_values=[""])
        meta["declared_domains"] = {a: sorted(g["correct_val"].dropna().unique().tolist())
                                    for a, g in gt.groupby("attribute")}
    return df, meta


# --------------------------------------------------------------------------- IPUMS-CPS (DPXPlain)

IPUMS_CODED = ["RELATE", "SEX", "RACE", "MARST", "CITIZEN", "CLASSWKR", "EDUC"]


def _ipums_codebook(xml_path: Path) -> dict:
    import xml.etree.ElementTree as ET

    tag = lambda e: e.tag.split("}")[-1]  # noqa: E731
    code: dict = {}
    for var in ET.parse(xml_path).getroot().iter():
        if tag(var) == "var" and var.get("ID") in IPUMS_CODED:
            d = {}
            for c in var:
                if tag(c) == "catgry":
                    v = [x.text for x in c if tag(x) == "catValu"]
                    lab = [x.text for x in c if tag(x) == "labl"]
                    if v and lab:
                        d[int(v[0])] = lab[0]
            code[var.get("ID")] = d
    return code


def load_ipums(raw_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """IPUMS-CPS exactly as prepared by DPXPlain (``data/ipums/ipumscps.py`` in its repository).

    Years 2011-2019, 0 < INCTOT < 200,000 (1,146,552 rows); AGE cut into decades;
    coded attributes mapped to their labels with the extract's XML codebook.
    The prepared relation is cached as ``ipumscps.csv``.
    """
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    d = raw_dir / "ipums"
    cached = d / "ipumscps.csv"
    meta = {"source": "IPUMS-CPS extract of DPXPlain (github.com/yuchaotao/Private-Explanation-System)",
            "synthetic": False}
    if cached.exists():
        return pd.read_csv(cached), meta
    if not (d / "cps_00005.csv.gz").exists() or not (d / "cps_00005.xml").exists():
        fetch("ipums", raw_dir)
    cols = ["YEAR", "MARST", "RELATE", "SEX", "RACE", "CITIZEN", "CLASSWKR", "AGE", "EDUC", "INCTOT"]
    df = pd.read_csv(d / "cps_00005.csv.gz", usecols=lambda c: c in cols)
    df = df.query("2011 <= YEAR <= 2019 and 0 < INCTOT < 200000").copy()
    df["AGE"] = pd.cut(df["AGE"], bins=np.linspace(0, 100, 11).astype(int)).astype(str)
    for col, mapping in _ipums_codebook(d / "cps_00005.xml").items():
        df[col] = df[col].map(mapping)
    df = df[cols].reset_index(drop=True)
    df.to_csv(cached, index=False)
    return df, meta


# --------------------------------------------------------------------------- StackOverflow

SO_REMOTE = {
    "Remote": "Fully remote",
    "Fully remote": "Fully remote",
    "In-person": "On-site",
    "Full in-person": "On-site",
    "Hybrid (some remote, some in-person)": "Hybrid",
}
SO_AI = {"Yes": "Yes", "No, and I don't plan to": "No", "No, but I plan to soon": "Plan"}
SO_ORG = {
    "Just me - I am a freelancer, sole proprietor, etc.": "1",
    "2 to 9 employees": "2-9",
    "10 to 19 employees": "10-99",
    "20 to 99 employees": "10-99",
    "100 to 499 employees": "100-999",
    "500 to 999 employees": "100-999",
    "1,000 to 4,999 employees": "1k-10k",
    "5,000 to 9,999 employees": "1k-10k",
    "10,000 or more employees": "10k+",
    "I don’t know": "Unknown",
    "I don't know": "Unknown",
}
SO_ED = {
    "Bachelor’s degree (B.A., B.S., B.Eng., etc.)": "Bachelor",
    "Master’s degree (M.A., M.S., M.Eng., MBA, etc.)": "Master",
    "Professional degree (JD, MD, Ph.D, Ed.D, etc.)": "Doctoral/Prof",
    "Some college/university study without earning a degree": "Some college",
    "Associate degree (A.A., A.S., etc.)": "Associate",
    "Secondary school (e.g. American high school, German Realschule or Gymnasium, etc.)": "Secondary",
    "Primary/elementary school": "Primary",
    "Something else": "Other",
}


def _so_from_survey(path: Path) -> pd.DataFrame:
    cols = ["RemoteWork", "AISelect", "YearsCodePro", "OrgSize", "Country", "Age", "EdLevel", "DevType",
            "LanguageHaveWorkedWith", "JobSat", "ConvertedCompYearly", "MainBranch"]
    raw = pd.read_csv(path, usecols=lambda c: c in cols, dtype=str, low_memory=False)
    df = pd.DataFrame()
    df["WorkRemote"] = raw["RemoteWork"].map(SO_REMOTE)
    df["UsingAI"] = raw["AISelect"].map(SO_AI)
    ycp = raw["YearsCodePro"].replace({"Less than 1 year": "0", "More than 50 years": "51"})
    df["YearsCodePro"] = pd.to_numeric(ycp, errors="coerce")
    df["OrgSize"] = raw["OrgSize"].map(SO_ORG)
    df["Country"] = raw["Country"].replace({
        "United States of America": "USA",
        "United Kingdom of Great Britain and Northern Ireland": "UK",
    })
    df["Age"] = raw["Age"].str.replace(" years old", "", regex=False)
    df["EdLevel"] = raw["EdLevel"].map(SO_ED)
    df["DevType"] = raw["DevType"].str.split(",").str[0].str.replace("Developer", "Dev", regex=False)
    df["UsesPython"] = raw["LanguageHaveWorkedWith"].fillna("").str.split(";").apply(lambda l: "Yes" if "Python" in l else "No")
    df["JobSat"] = pd.to_numeric(raw.get("JobSat"), errors="coerce")
    df["CompYearly"] = pd.to_numeric(raw["ConvertedCompYearly"], errors="coerce")
    df = df[df["WorkRemote"].notna() & df["YearsCodePro"].notna()].reset_index(drop=True)
    return df


def synthetic_stackoverflow(n: int = 65_437, seed: int = 2024) -> pd.DataFrame:
    """A synthetic stand-in for the developer survey with the normalised schema.

    Marginals loosely follow the 2024 survey report; dependencies are planted
    between age, experience, remote work, organisation size, AI usage and job
    satisfaction so that the S1-S3 contrasts have something to explain.  This is
    **not** the survey: results on it must be reported as synthetic.
    """
    rng = np.random.default_rng(seed)
    age_levels = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    age = rng.choice(len(age_levels), size=n, p=[0.17, 0.39, 0.25, 0.12, 0.05, 0.02])
    base_years = np.array([1.5, 5.0, 11.0, 18.0, 25.0, 32.0])[age]
    years = np.clip(np.round(rng.gamma(shape=3.0, scale=base_years / 3.0)), 0, 51)
    countries = ["USA", "Germany", "India", "UK", "Ukraine", "France", "Canada", "Poland", "Netherlands", "Brazil", "Other"]
    cp = np.array([0.18, 0.07, 0.07, 0.05, 0.04, 0.035, 0.035, 0.03, 0.025, 0.03, 0.43])
    country = rng.choice(len(countries), size=n, p=cp / cp.sum())
    orgs = ["1", "2-9", "10-99", "100-999", "1k-10k", "10k+", "Unknown"]
    org = rng.choice(len(orgs), size=n, p=[0.06, 0.09, 0.26, 0.24, 0.14, 0.17, 0.04])
    # remote work: more remote in small orgs, for the experienced, and in some countries
    logit_remote = -0.6 + 0.05 * np.minimum(years, 20) - 0.25 * (org >= 4) + 0.6 * (org <= 1) + 0.4 * np.isin(country, [4, 7, 9])
    logit_onsite = -1.1 + 0.35 * (org >= 4) + 0.45 * (country == 2) - 0.04 * np.minimum(years, 20)
    z = np.stack([logit_remote, np.zeros(n), logit_onsite], axis=1)
    p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
    remote = (rng.random((n, 1)) > p.cumsum(axis=1)).sum(axis=1)
    remote_levels = ["Fully remote", "Hybrid", "On-site"]
    # AI usage: younger and less experienced use AI more
    p_ai = 1 / (1 + np.exp(-(1.2 - 0.25 * age - 0.02 * years + 0.2 * (remote == 0))))
    ai_draw = rng.random(n)
    ai = np.where(ai_draw < p_ai, 0, np.where(rng.random(n) < 0.45, 2, 1))
    ai_levels = ["Yes", "No", "Plan"]
    eds = ["Bachelor", "Master", "Doctoral/Prof", "Some college", "Associate", "Secondary", "Primary", "Other"]
    ed = rng.choice(len(eds), size=n, p=[0.42, 0.23, 0.04, 0.12, 0.03, 0.12, 0.01, 0.03])
    devs = ["Dev, full-stack", "Dev, back-end", "Dev, front-end", "Dev, desktop or enterprise applications",
            "Dev, mobile", "Engineering manager", "Data scientist or machine learning specialist", "Other"]
    dev = rng.choice(len(devs), size=n, p=[0.3, 0.2, 0.06, 0.05, 0.04, 0.04, 0.04, 0.27])
    py = rng.random(n) < (0.35 + 0.35 * (dev == 6) + 0.05 * (ed == 2))
    # job satisfaction (0-10): remote and senior people are happier; AI users slightly so
    js = 6.3 + 0.6 * (remote == 0) - 0.5 * (remote == 2) + 0.03 * np.minimum(years, 25) + 0.3 * (ai == 0) + rng.normal(0, 2.0, n)
    js = np.clip(np.round(js), 0, 10)
    comp = np.exp(10.4 + 0.5 * (country == 0) - 0.9 * (country == 2) + 0.04 * np.minimum(years, 30) + rng.normal(0, 0.6, n))
    df = pd.DataFrame({
        "WorkRemote": np.array(remote_levels)[remote],
        "UsingAI": np.array(ai_levels)[ai],
        "YearsCodePro": years,
        "OrgSize": np.array(orgs)[org],
        "Country": np.array(countries)[country],
        "Age": np.array(age_levels)[age],
        "EdLevel": np.array(eds)[ed],
        "DevType": np.array(devs)[dev],
        "UsesPython": np.where(py, "Yes", "No"),
        "JobSat": js,
        "CompYearly": np.round(comp, -2),
    })
    return df


def load_stackoverflow(raw_dir: Path | None = None, allow_synthetic: bool = True, synthetic_rows: int = 65_437,
                       seed: int = 2024) -> tuple[pd.DataFrame, dict]:
    raw_dir = Path(raw_dir or DEFAULT_RAW_DIR)
    path = raw_dir / "stackoverflow" / "survey_results_public.csv"
    if not path.exists():
        info = fetch("stackoverflow", raw_dir)
        if not path.exists() and not allow_synthetic:
            raise FileNotFoundError("; ".join(info["errors"]))
    if path.exists():
        return _so_from_survey(path), {"source": str(path), "synthetic": False}
    warnings.warn(
        "StackOverflow survey file not available; using the SYNTHETIC generator "
        "(results must not be quoted as survey numbers).",
        stacklevel=2,
    )
    return synthetic_stackoverflow(synthetic_rows, seed), {"source": "synthetic_stackoverflow", "synthetic": True, "seed": seed}


LOADERS = {
    "adult": load_adult,
    "tax": load_tax,
    "tax_dirty": load_tax_dirty,
    "hospital": load_hospital,
    "stackoverflow": load_stackoverflow,
    "ipums": load_ipums,
}
