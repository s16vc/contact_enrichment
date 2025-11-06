This is how to configure the prefect infrastructure
# Host machine
We need one docker compose to run on the host machine in GCP (compute engine) vm.
You can ssh in the machine and create a file: config.yaml.

docker compose -f conf.yaml up -d
docker compose -f conf.yaml down => for shutdown

After display the containers running using:
docker ps

Choose the first container and inspect it

docker exec -it <container_id> /bin/bash

You need to run the worker pool
The pool needs to be created before in the ui.

prefect worker start --pool "mainPool" &

Install all necessary dependencies
pip install openai

# Dev machine
python deploy.py

run a workflow using deployment id
curl -X POST "http://34.163.142.11:4200/api/deployments/2baf1751-8f97-4afc-b76e-6b3c43f5c9fb/create_flow_run"   -H "Content-Type: application/json"   -d '{
    "parameters": {
      "company_name": "YourCompany",
      "company_context": "Optional context",
      "deck_extract": null,
      "research_data": null,
      "benchmark_data": null
    }
  }'