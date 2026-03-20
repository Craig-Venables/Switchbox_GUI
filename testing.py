import numpy as np
import matplotlib.pyplot as plt


PMMA_TG_K = 378.0  # PMMA glass transition temperature in K
TOL_TG_K = 120   # Toluene glass transition temperature in K
K_FACTOR = 1.0     # Gordon–Taylor (or similar) constant


def gordon_temperature_c(pmma_tg_k: float,
                         solvent_tg_k: float,
                         k: float,
                         pmma_fraction: np.ndarray,
                         solvent_fraction: np.ndarray) -> np.ndarray:
    """
    Compute blend Tg in °C using a Gordon-type equation:

        Tg = (pmma_tg * pmma_frac + k * solvent_tg * solvent_frac)
             / (pmma_frac + k * solvent_frac) - 273.15
    """
    numerator = (pmma_tg_k * pmma_fraction) + (k * solvent_tg_k * solvent_fraction)
    denominator = pmma_fraction + (k * solvent_fraction)
    tg_k = numerator / denominator
    return tg_k - 273.15


def main() -> None:
    # Solvent weight fraction from 0 to 0.04 (0–4%) in steps of 0.001
    solvent_fraction = np.arange(0.0, 0.0401, 0.001)
    pmma_fraction = 1.0 - solvent_fraction
    toluene_percent = solvent_fraction * 100.0

    # K values to compare
    k_values = [1,1.5]

    # Compute Tg curves for each K
    tg_curves = {
        k: gordon_temperature_c(
            PMMA_TG_K,
            TOL_TG_K,
            k,
            pmma_fraction,
            solvent_fraction,
        )
        for k in k_values
    }

    # Verify the given example at 3% solvent fraction (0.03)
    sf_example = 0.03
    pf_example = 1.0 - sf_example
    tg_example_c = gordon_temperature_c(
        PMMA_TG_K,
        TOL_TG_K,
        K_FACTOR,
        np.array([pf_example]),
        np.array([sf_example]),
    )[0]
    print(f"(K = {K_FACTOR}) Tg at solvent fraction 0.03 ≈ {tg_example_c:.6f} °C (expected ≈ 100.814467 °C)")

    # Pure PMMA Tg in °C for reference
    tg_pure_pmma_c = PMMA_TG_K - 273.15

    # Temperature drop relative to pure PMMA for each K
    delta_t_curves = {k: tg_pure_pmma_c - tg for k, tg in tg_curves.items()}

    # Plot Tg (°C) vs % toluene
    plt.figure(figsize=(7, 5))
    for k, tg_c in tg_curves.items():
        plt.plot(toluene_percent, tg_c, label=f"Tg (°C), K={k}")
    plt.axhline(tg_pure_pmma_c, color="gray", linestyle="--", label="Pure PMMA Tg")
    plt.scatter([sf_example * 100.0], [tg_example_c], color="red", zorder=5,
                label=f"3% toluene, K={K_FACTOR}")
    plt.xlabel("Toluene weight (%)")
    plt.ylabel("Tg (°C)")
    plt.title("Gordon equation: PMMA/Toluene Tg vs toluene %")
    plt.legend()
    plt.tight_layout()

    # Plot temperature drop vs % toluene
    plt.figure(figsize=(7, 5))
    for k, delta_t in delta_t_curves.items():
        plt.plot(toluene_percent, delta_t, label=f"Tg drop (°C), K={k}")
    plt.scatter([sf_example * 100.0], [tg_pure_pmma_c - tg_example_c],
                color="red", zorder=5, label=f"3% toluene, K={K_FACTOR}")
    plt.xlabel("Toluene weight (%)")
    plt.ylabel("Tg drop relative to pure PMMA (°C)")
    plt.title("PMMA/Toluene Tg drop vs toluene %")
    plt.legend()
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()

