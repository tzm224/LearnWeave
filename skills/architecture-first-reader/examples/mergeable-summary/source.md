# A Mergeable Summary for Shifted Exponential Sums

This is an original synthetic technical note for evaluating a reading workflow, not a published paper or measured implementation.

## 1. Setting and aim

Given a nonempty finite sequence of finite real values x, compute log(sum(exp(x_i))). Direct exponentiation may overflow a floating-point implementation for large positive inputs. Shifting all values by their maximum avoids positive exponent arguments, but finding one global maximum before calculating a global shifted sum requires coordinating all chunks.

We consider inputs already partitioned into nonempty chunks. A chunk processor should emit a constant-size summary that can be combined in any binary tree without retaining the original chunk. We seek an exact identity over real arithmetic; no claim of identical floating-point bits across tree shapes is intended.

## 2. Representation

For a nonempty chunk A define m_A = max(x_i in A) and s_A = sum(exp(x_i - m_A) for i in A). The pair (m_A, s_A) represents the unshifted sum exp(m_A) * s_A, although an implementation need not form this potentially overflowing product.

For chunks A and B, let m = max(m_A, m_B) and merge to:

s = s_A * exp(m_A - m) + s_B * exp(m_B - m).

Return the pair (m, s). At the root, return m + log(s).

## 3. Why merge preserves the representation

Multiplying the merged s by exp(m) yields exp(m_A)*s_A + exp(m_B)*s_B, equal to the sum of exponentials over the union. The merged maximum is the maximum over that union. Thus the pair is the same canonical pair that would be computed for the union, in exact real arithmetic. Induction over a tree gives the full result and makes the operation associative in this arithmetic model.

The two rescaling exponents are nonpositive because m is at least each local maximum. Local summaries do not need the eventual global maximum: each merge changes their common reference before adding them. Simply adding s_A and s_B while choosing max(m_A,m_B) is incorrect when the maxima differ. For singleton chunks [0] and [log(2)], both local s values are 1, but the correct merged pair is (log(2), 1.5), not (log(2), 2).

## 4. Costs and limitations

Each chunk emits two scalars; each tree merge performs a bounded number of scalar arithmetic and exponential operations. This permits chunk-local work followed by a reduction tree. The note does not benchmark a GPU kernel or claim a speedup over a coordinated two-pass implementation. It does not compute each softmax probability: those would require revisiting or retaining individual inputs after the total is known.

Floating-point rescaling can underflow tiny contributions, rounding breaks exact associativity, and a balanced tree is not promised to give the same answer as a sequential fold. NaNs, infinite inputs and empty chunks are excluded; no identity element for an empty chunk is specified. The proof does not establish an error bound or show one implementation is more accurate than another.
