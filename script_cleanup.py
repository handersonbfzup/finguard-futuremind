"""script_cleanup.py — remove recursos do Amazon SageMaker eventualmente criados durante o
bônus de clusterização (Fase 4), evitando cobranças residuais depois do desafio.

Esta entrega optou por treinar o K-Means localmente com scikit-learn em vez de usar o
SageMaker SDK (ver adr_finguard.html, seção de custos), então normalmente NÃO há endpoints
para remover. O script fica disponível como rede de segurança, caso em algum momento um
endpoint/model de teste tenha sido criado manualmente na conta AWS durante a exploração.

Por segurança, o padrão é dry-run: o script só LISTA o que seria removido. Nada é apagado
sem a flag --confirm.

Uso:
  python3 script_cleanup.py                       # lista o que existe (não apaga nada)
  python3 script_cleanup.py --confirm             # remove de fato os recursos com prefixo "finguard"
  python3 script_cleanup.py --prefixo outro --confirm
"""

import argparse

from botocore.exceptions import ClientError, NoCredentialsError


def listar_recursos(cliente, prefixo: str) -> dict:
    recursos = {"endpoints": [], "endpoint_configs": [], "models": []}
    try:
        for pagina in cliente.get_paginator("list_endpoints").paginate():
            for endpoint in pagina["Endpoints"]:
                if endpoint["EndpointName"].startswith(prefixo):
                    recursos["endpoints"].append(endpoint["EndpointName"])
        for pagina in cliente.get_paginator("list_endpoint_configs").paginate():
            for config in pagina["EndpointConfigs"]:
                if config["EndpointConfigName"].startswith(prefixo):
                    recursos["endpoint_configs"].append(config["EndpointConfigName"])
        for pagina in cliente.get_paginator("list_models").paginate():
            for modelo in pagina["Models"]:
                if modelo["ModelName"].startswith(prefixo):
                    recursos["models"].append(modelo["ModelName"])
    except ClientError as erro:
        print(f"Erro ao listar recursos SageMaker: {erro}")
    return recursos


def remover_recursos(cliente, recursos: dict, confirmar: bool) -> None:
    for nome in recursos["endpoints"]:
        acao = "removendo" if confirmar else "seria removido (dry-run)"
        print(f"Endpoint: {nome} -> {acao}")
        if confirmar:
            cliente.delete_endpoint(EndpointName=nome)
    for nome in recursos["endpoint_configs"]:
        acao = "removendo" if confirmar else "seria removido (dry-run)"
        print(f"Endpoint config: {nome} -> {acao}")
        if confirmar:
            cliente.delete_endpoint_config(EndpointConfigName=nome)
    for nome in recursos["models"]:
        acao = "removendo" if confirmar else "seria removido (dry-run)"
        print(f"Model: {nome} -> {acao}")
        if confirmar:
            cliente.delete_model(ModelName=nome)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prefixo", default="finguard", help="prefixo de nome usado para filtrar os recursos SageMaker do projeto")
    parser.add_argument("--regiao", default="us-east-1")
    parser.add_argument("--confirm", action="store_true", help="de fato apaga; sem essa flag o script só lista (dry-run)")
    args = parser.parse_args()

    try:
        import boto3

        cliente = boto3.client("sagemaker", region_name=args.regiao)
        recursos = listar_recursos(cliente, args.prefixo)
    except NoCredentialsError:
        print("Sem credenciais AWS configuradas — nada para verificar/remover.")
        print("Configure com 'aws configure' antes de rodar este script contra uma conta real.")
        return

    total = sum(len(v) for v in recursos.values())
    if total == 0:
        print(f"Nenhum recurso SageMaker com prefixo '{args.prefixo}' encontrado na região {args.regiao}. Nada para limpar.")
        return

    remover_recursos(cliente, recursos, args.confirm)
    if not args.confirm:
        print("\nModo dry-run — nenhum recurso foi removido. Rode novamente com --confirm para remover de fato.")


if __name__ == "__main__":
    main()
