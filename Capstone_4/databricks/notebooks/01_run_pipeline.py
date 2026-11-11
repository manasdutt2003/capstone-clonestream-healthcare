# Databricks notebook source
# ruff: noqa
# CloneStream Healthcare (Capstone 4): unpack the project, run the whole pipeline, copy every table into Delta.
# Put each block between the "COMMAND" lines in its own cell if you paste this by hand.

# COMMAND ----------

# MAGIC %pip install duckdb openpyxl pyyaml

# COMMAND ----------

# Restarts Python so the install takes effect
dbutils.library.restartPython()

# COMMAND ----------

# Unpack the project and run it: the same as `python -m hcls all` on your PC (about 20 to 60 seconds)
import os, shutil, sys, zipfile

CATALOG = "workspace"
VOL = f"/Volumes/{CATALOG}/clonestream/raw"
WORK = "/tmp/clonestream"

shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
with zipfile.ZipFile(f"{VOL}/capstone4_src.zip") as z:
    for info in z.infolist():
        rel = info.filename.replace("\\", "/").lstrip("/")     # zips made by Windows PowerShell use backslashes
        dest = os.path.normpath(os.path.join(WORK, rel))
        if not rel or rel.endswith("/") or not dest.startswith(WORK + os.sep):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with z.open(info) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)

# The zip must have config.yaml, src/ and Resources/HCLS.xlsx directly at its top level
for need in ("config.yaml", "src/hcls/cli.py", "Resources/HCLS.xlsx"):
    assert os.path.exists(f"{WORK}/{need}"), f"'{need}' not found after unzipping. Re-make the zip from the project root folder."

os.environ.setdefault("USER", "databricks")     # the audit log records who ran the job
os.chdir(WORK)
sys.path.insert(0, f"{WORK}/src")

from hcls.cli import main
rc = main(["all"])
assert rc == 0, f"pipeline returned {rc}"

# COMMAND ----------

# Copy every table into Delta: bronze_*, silver_*, gold_* (plus gold_rc_* for the root-cause evidence)
import glob, re
import pandas as pd
from pyspark.sql.types import *

OUT = f"{WORK}/outputs"
BAD_CHARS = re.compile(r"[ ,;{}()\n\t=]")      # characters Delta does not allow in column names

def spark_type(s):
    k = s.dtype.kind
    return LongType() if k in "iu" else DoubleType() if k == "f" else BooleanType() if k == "b" else StringType()

def to_spark(pdf):
    pdf = pdf.rename(columns=lambda c: BAD_CHARS.sub("_", str(c)))
    fields = [StructField(c, spark_type(pdf[c]), True) for c in pdf.columns]
    def clean(v, f):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        t = f.dataType
        return int(v) if isinstance(t, LongType) else float(v) if isinstance(t, DoubleType) else bool(v) if isinstance(t, BooleanType) else str(v)
    rows = [tuple(clean(v, f) for v, f in zip(r, fields)) for r in pdf.itertuples(index=False, name=None)]
    return spark.createDataFrame(rows, StructType(fields))

sources = []
for layer in ("bronze", "silver"):
    sources += [(f"{layer}_", f, "parquet") for f in sorted(glob.glob(f"{OUT}/{layer}/*.parquet"))]
sources += [("gold_", f, "csv") for f in sorted(glob.glob(f"{OUT}/gold/*.csv"))]
sources += [("gold_rc_", f, "csv") for f in sorted(glob.glob(f"{OUT}/gold/rootcause/*.csv"))]

loaded, failed = [], []
for prefix, f, kind in sources:
    name = prefix + re.sub(r"[^0-9a-zA-Z_]", "_", os.path.splitext(os.path.basename(f))[0]).lower()
    try:
        pdf = pd.read_parquet(f) if kind == "parquet" else pd.read_csv(f)
        to_spark(pdf).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.clonestream.{name}")
        loaded.append(name)
    except Exception as e:
        failed.append((name, str(e)[:150]))
print(len(loaded), "tables written; failed:", failed)

# COMMAND ----------

# Check it matches your local run
from pyspark.sql import functions as F

def total(prefix):
    return sum(spark.table(f"{CATALOG}.clonestream.{n}").count() for n in loaded if n.startswith(prefix))

sc = spark.table(f"{CATALOG}.clonestream.gold_dq_scorecard")
print("bronze rows:", total("bronze_"), "| silver rows:", total("silver_"))
print("findings:", sc.filter((F.col("rows_failed") > 0) & (F.col("severity") != "Info")).count(),
      "| Critical failing:", sc.filter((F.col("rows_failed") > 0) & (F.col("severity") == "Critical")).count())
display(spark.table(f"{CATALOG}.clonestream.gold_audit_metrics"))
