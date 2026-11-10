"""Verifica o ambiente Python do TG-005.

Importa as bibliotecas instaladas e carrega um conjunto de dados de exemplo
(Iris), sem treinar nenhum modelo. Isso fica para a TG-006.
"""

import sklearn
from sklearn.datasets import load_iris


def main() -> None:
    print(f"scikit-learn {sklearn.__version__}")

    iris = load_iris()
    classes = [str(name) for name in iris.target_names]
    print(f"Exemplo carregado: Iris, {iris.data.shape[0]} amostras, "
          f"{iris.data.shape[1]} atributos, classes {classes}")


if __name__ == "__main__":
    main()
