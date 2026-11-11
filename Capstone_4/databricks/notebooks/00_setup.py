# Databricks notebook source
# ruff: noqa
# Run once. Creates the schema (a folder for tables) and the volume (a folder for files).
# Check your catalog name under Catalog in the left menu. On Free Edition it is usually "workspace".

# COMMAND ----------

CATALOG = "workspace"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.clonestream")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.clonestream.raw")
print("ready:", f"/Volumes/{CATALOG}/clonestream/raw")
