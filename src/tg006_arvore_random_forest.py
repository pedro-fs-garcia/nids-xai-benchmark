"""TG-006: treinar uma árvore de decisão e um Random Forest no Iris.

Usa o conjunto Iris (já carregado na TG-005) para passar pelo fluxo completo:
separar treino/teste, treinar os dois modelos, prever no conjunto de teste e
visualizar uma árvore rasa. Nenhum dado do CIC-IDS2017 é usado aqui.
"""

from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

RANDOM_STATE = 42


def main() -> None:
    iris = load_iris()
    X, y = iris.data, iris.target  # X: atributos (4 medidas da flor); y: rótulo (espécie)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=RANDOM_STATE
    )
    print(f"Treino: {X_train.shape[0]} amostras | Teste: {X_test.shape[0]} amostras")

    # Criar o modelo apenas define os hiperparâmetros; ele ainda não "sabe" nada.
    tree = DecisionTreeClassifier(max_depth=3, random_state=RANDOM_STATE)
    forest = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)

    # fit(): é aqui que o modelo aprende, a partir dos dados de treino.
    tree.fit(X_train, y_train)
    forest.fit(X_train, y_train)

    for name, model in [("Árvore de decisão", tree), ("Random Forest", forest)]:
        # predict()/predict_proba(): usam o modelo já treinado, sem alterá-lo.
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)
        acc = accuracy_score(y_test, y_pred)
        print(f"\n{name}")
        print(f"  Acurácia no teste: {acc:.3f}")
        print(f"  predict (5 primeiras): {y_pred[:5]}")
        print(f"  predict_proba (1ª amostra): {y_proba[0].round(3)}")

    print("\nÁrvore de decisão rasa (profundidade 3):")
    print(export_text(tree, feature_names=list(iris.feature_names)))


if __name__ == "__main__":
    main()
