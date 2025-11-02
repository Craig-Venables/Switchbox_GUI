# Relaxation Time (τ) - Explanation

## Units

**Tau (τ) has the same units as your X-axis data.**

- If your X-axis is **Time (s)**, then τ is in **seconds**
- If your X-axis is **Time (ms)**, then τ is in **milliseconds**
- If your X-axis is **Voltage (V)**, then τ would be in **volts** (unusual case)

For most TSP measurements, **τ is in seconds** since the data is typically time series data.

### Example:
- If τ = **15.5**, that means the relaxation time constant is **15.5 seconds**
- If τ = **0.001**, that means **1 millisecond**

---

## How Tau is Calculated

### Mathematical Model

Tau is calculated by fitting your data to an **exponential relaxation function**:

**For Decay (decreasing values):**
```
y(t) = y∞ + (y₀ - y∞) × exp(-t/τ)
```

**For Growth (increasing values):**
```
y(t) = y∞ - (y∞ - y₀) × exp(-t/τ)
```

Where:
- **y(t)** = Value at time t
- **y₀** = Initial value (at t=0)
- **y∞** = Final equilibrium value (as t → ∞)
- **τ** = Relaxation time constant (tau)
- **t** = Time
- **exp()** = Exponential function (e^x)

### Physical Meaning

**τ (tau) is the time constant** - it represents:
- **Time for ~63% of the total change to occur**
- For decay: Time to drop 63% of the way from y₀ to y∞
- For growth: Time to rise 63% of the way from y₀ to y∞

After **3τ**, about **95%** of the change has occurred.  
After **5τ**, about **99%** of the change has occurred.

---

## Calculation Process

### Step 1: Detect Relaxation Type
The algorithm checks if your data is:
- **Growth**: Final value > Initial value (increasing)
- **Decay**: Final value < Initial value (decreasing)

### Step 2: Initial Guess
Estimates initial tau by finding the time point where the data reaches ~63% of the total change.

### Step 3: Curve Fitting
Uses **nonlinear least-squares curve fitting** (scipy.optimize.curve_fit) to find the best-fit parameters:
- y∞ (equilibrium value)
- y₀ (initial value)
- **τ (relaxation time)** ← This is what we want!

### Step 4: Validation
- Calculates **R²** (coefficient of determination) to measure fit quality
- R² > 0.95 = Excellent fit
- R² > 0.90 = Good fit
- R² < 0.90 = Poor fit (may not be exponential)

### Step 5: Error Estimation
Calculates standard error of tau from the covariance matrix.

---

## Interpretation

### What Does Tau Tell You?

**Small τ (e.g., 0.1 s):**
- Fast relaxation
- System reaches equilibrium quickly
- Less "memory" of initial state

**Large τ (e.g., 1000 s):**
- Slow relaxation
- System takes a long time to reach equilibrium
- Strong "memory" of initial state

### Example Scenarios

**Resistance Relaxation:**
- τ = 5 s → Resistance relaxes to equilibrium in ~5 seconds
- After 15 s (3τ), resistance is 95% of the way to equilibrium

**Current Decay:**
- τ = 0.5 s → Current decays quickly
- Most change happens in the first 0.5 seconds

---

## Sign Handling

The algorithm ensures **τ is always positive**:
- Takes absolute value if curve fitting produces negative tau
- Negative tau can occur for growth processes but is mathematically equivalent to positive tau
- The sign is handled automatically by the exponential function

**You don't need to worry about signs** - tau is always reported as a positive number representing the time constant.

---

## Quality Indicators

When interpreting tau, check:

1. **R² Value:**
   - High R² (≥0.95) = Reliable tau
   - Low R² (<0.90) = May not be exponential, tau may be unreliable

2. **Tau Error:**
   - Small error relative to tau = Precise measurement
   - Large error = Uncertain measurement

3. **Data Coverage:**
   - Need at least 4 data points
   - Better fits with more points spanning the relaxation range

4. **Data Quality:**
   - Noisy data = Less reliable tau
   - Smooth exponential = More reliable tau

---

## Limitations

**Tau calculation assumes:**
- Data follows an exponential function
- Single relaxation process (not multiple processes)
- No external disturbances during measurement

**If your data doesn't fit well (low R²):**
- May have multiple relaxation processes
- May have non-exponential behavior
- May need to crop data to exponential region only

---

## Example Calculation

For your relaxation file:
- **X-axis:** Time (s)
- **Y-axis:** Resistance (Ω)
- **Initial Resistance:** y₀ ≈ 117,600 Ω
- **Final Resistance:** y∞ ≈ 100,000 Ω

If tau = **15.5 s**, that means:
- Resistance relaxes from 117,600 Ω toward 100,000 Ω
- After **15.5 seconds**, resistance has changed by 63% of (117,600 - 100,000) = 63% of 17,600 = 11,088 Ω
- So after 15.5 s, resistance ≈ 117,600 - 11,088 = **106,512 Ω**
- After **46.5 s** (3τ), resistance ≈ **103,600 Ω** (95% complete)
- After **77.5 s** (5τ), resistance ≈ **101,700 Ω** (99% complete)

---

**In Summary:**
- **Units:** Same as X-axis (typically seconds)
- **Calculation:** Exponential curve fitting
- **Meaning:** Time for 63% of change to occur
- **Always positive** (sign handled automatically)
- **Check R²** to verify fit quality



