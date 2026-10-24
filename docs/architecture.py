"""Architecture diagram as code.

Regenerate docs/architecture.png after any change to the pipeline:

    pip install diagrams      # also needs Graphviz: sudo apt install graphviz
    python docs/architecture.py
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.analytics import Athena
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SNS, EventbridgeScheduler
from diagrams.aws.storage import S3
from diagrams.onprem.analytics import Dbt, Metabase
from diagrams.onprem.network import Internet
from diagrams.onprem.workflow import Airflow

OUT = Path(__file__).with_name("architecture")

graph_attr = {"pad": "0.5", "nodesep": "0.7", "ranksep": "1.0", "fontsize": "16"}

with Diagram(
    "dc-bikeshare-lakehouse",
    filename=str(OUT),
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    with Cluster("Sources"):
        gbfs = Internet("GBFS station status")
        trips = Internet("Monthly trip files")
        weather = Internet("Open-Meteo weather")

    with Cluster("AWS · Terraform"):
        scheduler = EventbridgeScheduler("Scheduler\nevery 15 min")
        ingest = Lambda("Ingest Lambda\n(container image)")
        alerts = SNS("SNS alerts")

        with Cluster("S3 lake · Glue catalog · Athena"):
            bronze = S3("bronze\nraw files")
            silver = S3("silver\nIceberg MERGE")
            gold = S3("gold\nIceberg rebuild")
            athena = Athena("Athena\nworkgroup bikeshare")

    with Cluster("Laptop · Docker"):
        airflow = Airflow("Airflow\ndaily + monthly")
        dbt = Dbt("dbt-athena")
        metabase = Metabase("Metabase\n(read-only)")

    [gbfs, trips, weather] >> ingest
    scheduler >> ingest
    ingest >> bronze
    ingest >> Edge(style="dashed", label="failures") >> alerts

    airflow >> Edge(label="trips, weather") >> ingest
    airflow >> dbt >> Edge(label="SQL") >> athena
    bronze >> silver >> gold
    gold >> Edge(label="queries") >> metabase
