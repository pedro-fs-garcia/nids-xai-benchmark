"""TG-007, parte 1: matriz de confusão e métricas de classificação.

Usa só versicolor e virginica do Iris (as duas classes que realmente se
confundem; setosa é trivialmente separável e não gera erros). Positivo =
virginica (1), negativo = versicolor (0).
"""

import numpy as np
from sklearn.datasets import load_iris
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                              recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

RANDOM_STATE = 42


def main() -> None:
    iris = load_iris()
    mask = iris.target != 0  # remove setosa
    X = iris.data[mask]
    y = (iris.target[mask] == 2).astype(int)  # 1 = virginica, 0 = versicolor

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=RANDOM_STATE
    )

    model = DecisionTreeClassifier(max_depth=3, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    print("Matriz de confusão (positivo = virginica):")
    print(f"  TN={tn}  FP={fp}")
    print(f"  FN={fn}  TP={tp}")

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    fpr_value = fp / (fp + tn) if (fp + tn) else float("nan")
    auc = roc_auc_score(y_test, y_proba)

    print(f"\nPrecisão: {precision:.3f}")
    print(f"Recall (sensibilidade): {recall:.3f}")
    print(f"F1: {f1:.3f}")
    print(f"Taxa de falsos positivos (FPR): {fpr_value:.3f}")
    print(f"ROC AUC: {auc:.3f}")

    fpr_curve, tpr_curve, thresholds = roc_curve(y_test, y_proba)
    print("\nCurva ROC (amostrada): limiar | FPR | TPR")
    step = max(len(thresholds) // 5, 1)
    for i in range(0, len(thresholds), step):
        print(f"  {thresholds[i]:.3f} | {fpr_curve[i]:.3f} | {tpr_curve[i]:.3f}")

    errors = np.where(y_pred != y_test)[0]
    fp_idx = next((i for i in errors if y_pred[i] == 1 and y_test[i] == 0), None)
    fn_idx = next((i for i in errors if y_pred[i] == 0 and y_test[i] == 1), None)

    print("\nExemplos de erro no conjunto de teste:")
    if fp_idx is not None:
        print(f"  Falso positivo (índice {fp_idx}): atributos {X_test[fp_idx].round(2)}, "
              f"rótulo real=versicolor, previsto=virginica, "
              f"P(virginica)={y_proba[fp_idx]:.3f}")
    else:
        print("  Nenhum falso positivo neste conjunto de teste.")

    if fn_idx is not None:
        print(f"  Falso negativo (índice {fn_idx}): atributos {X_test[fn_idx].round(2)}, "
              f"rótulo real=virginica, previsto=versicolor, "
              f"P(virginica)={y_proba[fn_idx]:.3f}")
    else:
        print("  Nenhum falso negativo neste conjunto de teste.")


if __name__ == "__main__":
    main()
