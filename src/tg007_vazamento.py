"""TG-007, parte 2: um exemplo medido de vazamento de dados.

Reproduz em miniatura o problema real do CIC-IDS2017: há 22.109 registros em
grupos com atributos de tráfego idênticos (relatorios/inspecao-cicids2017.md).
Se a divisão treino/teste ignorar esses grupos, uma cópia de um registro pode
"vazar" do treino para o teste, inflando artificialmente o desempenho.

Aqui o mesmo mecanismo é simulado nas 100 linhas de versicolor/virginica do
Iris (as duas classes que se confundem; com setosa incluída o 1-NN já acerta
perto de 100% mesmo sem vazar nada, e o efeito do vazamento ficaria escondido
atrás desse teto). 20 dessas linhas são duplicadas, e um k-NN(1) é usado
porque reage de forma extrema ao vazamento: se o gêmeo exato de um caso de
teste está no treino, a distância entre eles é zero e o acerto é garantido
pelo próprio mecanismo do algoritmo, não por sorte de amostragem.
"""

import numpy as np
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.neighbors import KNeighborsClassifier

RANDOM_STATE = 42


def main() -> None:
    iris = load_iris()
    mask = iris.target != 0  # mantém só versicolor/virginica: são as que se confundem
    X, y = iris.data[mask], iris.target[mask]  # com setosa, o 1-NN já acerta ~100% sem vazar nada
    n = len(y)
    groups = np.arange(n)  # cada linha original é seu próprio grupo

    rng = np.random.default_rng(RANDOM_STATE)
    dup_idx = rng.choice(n, size=20, replace=False)

    X_aug = np.vstack([X, X[dup_idx]])
    y_aug = np.concatenate([y, y[dup_idx]])
    groups_aug = np.concatenate([groups, groups[dup_idx]])  # cópia herda o grupo do original

    print(f"Dataset aumentado: {len(y_aug)} linhas, {len(set(groups_aug))} grupos "
          f"({len(dup_idx)} grupos duplicados).")

    # --- Divisão ingênua: ignora os grupos, como um split por linha no CSV ---
    X_tr, X_te, y_tr, y_te, g_tr, g_te = train_test_split(
        X_aug, y_aug, groups_aug, test_size=0.3, stratify=y_aug, random_state=RANDOM_STATE
    )
    leaked_mask = np.isin(g_te, g_tr)
    print(f"\nDivisão ingênua: {leaked_mask.sum()} de {len(g_te)} linhas de teste "
          f"têm seu par duplicado no treino (vazamento).")

    knn = KNeighborsClassifier(n_neighbors=1)
    knn.fit(X_tr, y_tr)
    y_pred = knn.predict(X_te)

    acc_leaked = accuracy_score(y_te[leaked_mask], y_pred[leaked_mask]) if leaked_mask.any() else float("nan")
    acc_clean = accuracy_score(y_te[~leaked_mask], y_pred[~leaked_mask])
    print(f"  Acurácia nas linhas vazadas: {acc_leaked:.3f} (n={leaked_mask.sum()})")
    print(f"  Acurácia nas linhas não vazadas: {acc_clean:.3f} (n={(~leaked_mask).sum()})")

    # --- Divisão correta: mantém cada grupo inteiro de um só lado ---
    gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(X_aug, y_aug, groups_aug))
    assert not set(groups_aug[train_idx]) & set(groups_aug[test_idx]), "grupo cruzou treino/teste"

    knn_grouped = KNeighborsClassifier(n_neighbors=1)
    knn_grouped.fit(X_aug[train_idx], y_aug[train_idx])
    y_pred_grouped = knn_grouped.predict(X_aug[test_idx])
    acc_grouped = accuracy_score(y_aug[test_idx], y_pred_grouped)

    print(f"\nDivisão por grupo (nenhum par dividido): acurácia = {acc_grouped:.3f} "
          f"(n={len(test_idx)})")
    print("\nConclusão: a acurácia nas linhas vazadas reflete memorização do par "
          "duplicado, não generalização. A acurácia nas linhas não vazadas e na "
          "divisão por grupo é a estimativa honesta do desempenho do modelo.")


if __name__ == "__main__":
    main()
