import re
import itertools

class CompoundNameMatcher:
    TITLES_TO_STRIP = {
        "mr", "mrs", "ms", "miss", "dr", "prof", "professor",
        "sir", "lord", "lady", "dame", "rev", "reverend", 
        "fr", "father", "sr", "senior", "jr", "junior",
        "ii", "iii", "iv", "v", "phd", "md", "hon", "honorable", "st", "saint"
    }

    def __init__(self, base_matcher):
        """
        Wraps the core NameMatcherWrapper.
        base_matcher: An initialized instance of NameMatcherWrapper.
        """
        self.base_matcher = base_matcher

    def tokenize(self, name):
        """Splits a compound name into a list of normalized tokens, stripping titles/suffixes."""
        # Split on spaces, hyphens, underscores, dots and filter empty strings
        raw_tokens = [t.strip() for t in re.split(r'[\s\-_.]+', name) if t.strip()]
        
        # Filter out common titles and suffixes to prevent match pollution
        clean_tokens = [t for t in raw_tokens if t.lower() not in self.TITLES_TO_STRIP]
        
        # Fallback: If they literally just typed "Lord" vs "Lord", return raw to prevent empty index crashes
        return clean_tokens if clean_tokens else raw_tokens

    def _generate_splits(self, token, parts):
        """Generates all ways to split `token` into `parts` non-empty substrings."""
        if len(token) < parts:
            return []
        splits = []
        for split_indices in itertools.combinations(range(1, len(token)), parts - 1):
            parts_list = []
            last_idx = 0
            for idx in split_indices:
                parts_list.append(token[last_idx:idx])
                last_idx = idx
            parts_list.append(token[last_idx:])
            splits.append(parts_list)
        return splits

    def evaluate(self, name1, name2, compound_strategy="symmetrical", 
                 use_carlton=True, use_wikidata=True, use_jrc=True, use_l2=True,
                 strict_order=False, allow_initials=True, strict_unknowns=False, allow_stepwise=False):
        """
        Evaluates compound names by tokenizing and performing optimal bipartite matching.
        If strict_order is True, it performs a sequential comparison instead of optimal alignment.
        If allow_stepwise is True, it will attempt to split long tokens if token counts differ.
        """
        tokens1 = self.tokenize(name1)
        tokens2 = self.tokenize(name2)
        
        # --- Guardrail: Pure Initials ---
        if tokens1 and all(len(t) == 1 for t in tokens1):
            return {"name1": name1, "name2": name2, "match": False, "confidence": 0.0, 
                    "explanation": "Guardrail Triggered: Target Entity A contains purely initials and lacks sufficient character entropy."}
        if tokens2 and all(len(t) == 1 for t in tokens2):
            return {"name1": name1, "name2": name2, "match": False, "confidence": 0.0, 
                    "explanation": "Guardrail Triggered: Target Entity B contains purely initials and lacks sufficient character entropy."}
        
        # Fast path: If both names are single tokens
        if len(tokens1) <= 1 and len(tokens2) <= 1:
            t1_eval = tokens1[0] if tokens1 else name1
            t2_eval = tokens2[0] if tokens2 else name2
            res = self.base_matcher.evaluate(t1_eval, t2_eval, use_carlton, use_wikidata, use_jrc, use_l2, strict_unknowns)
            res["name1"] = name1
            res["name2"] = name2
            return res
            
        N = len(tokens1)
        M = len(tokens2)
        
        # --- Phase 18: Stepwise Substring Matching ---
        stepwise_best_res = None
        if allow_stepwise and N != M:
            best_stepwise_score = -1.0
            
            if N < M:
                parts_needed = (M - N) + 1
                for i, token in enumerate(tokens1):
                    if len(token) >= parts_needed:
                        for split_parts in self._generate_splits(token, parts_needed):
                            new_tokens1 = tokens1[:i] + split_parts + tokens1[i+1:]
                            new_name1 = " ".join(new_tokens1)
                            # Recursive call with allow_stepwise=False to prevent infinite loop
                            res = self.evaluate(new_name1, name2, compound_strategy, use_carlton, use_wikidata, use_jrc, use_l2, strict_order, allow_initials, strict_unknowns, allow_stepwise=False)
                            if res['confidence'] > best_stepwise_score:
                                best_stepwise_score = res['confidence']
                                stepwise_best_res = dict(res)
                                stepwise_best_res['explanation'] += f" [Stepwise Resolved: '{token}' -> '{" ".join(split_parts)}']"
                                
            elif M < N:
                parts_needed = (N - M) + 1
                for i, token in enumerate(tokens2):
                    if len(token) >= parts_needed:
                        for split_parts in self._generate_splits(token, parts_needed):
                            new_tokens2 = tokens2[:i] + split_parts + tokens2[i+1:]
                            new_name2 = " ".join(new_tokens2)
                            res = self.evaluate(name1, new_name2, compound_strategy, use_carlton, use_wikidata, use_jrc, use_l2, strict_order, allow_initials, strict_unknowns, allow_stepwise=False)
                            if res['confidence'] > best_stepwise_score:
                                best_stepwise_score = res['confidence']
                                stepwise_best_res = dict(res)
                                stepwise_best_res['explanation'] += f" [Stepwise Resolved: '{token}' -> '{" ".join(split_parts)}']"

        # Symmetrical Guard
        if compound_strategy == "symmetrical" and N != M:
            baseline_res = {
                "name1": name1, "name2": name2,
                "match": False, "confidence": 0.0,
                "explanation": f"Strict Symmetrical Mismatch: Token counts differ ({N} vs {M})."
            }
            # If symmetrical strictly fails normally, but stepwise found a match, return stepwise!
            if stepwise_best_res and stepwise_best_res['confidence'] > baseline_res['confidence']:
                stepwise_best_res['name1'] = name1 # Ensure original input names are preserved in output
                stepwise_best_res['name2'] = name2
                return stepwise_best_res
            return baseline_res

        # --- Strict Order Logic ---
        if strict_order:
            total_score = 0.0
            mapping_details = []
            global_gender_mismatch = False
            mismatch_pair = ""
            
            # Compare tokens sequentially up to the shortest list
            for i in range(min(N, M)):
                t1, t2 = tokens1[i], tokens2[i]
                
                # Check for Initials
                t1_clean, t2_clean = t1.lower(), t2.lower()
                is_initial_t1 = len(t1_clean) == 1
                is_initial_t2 = len(t2_clean) == 1
                
                if (is_initial_t1 or is_initial_t2) and not allow_initials:
                    conf, expl = 0.0, f"Initials Disallowed ({t1} <-> {t2})"
                elif is_initial_t1 or is_initial_t2:
                    # Resolve initials
                    if t1_clean == t2_clean: conf, expl = 1.0, f"Exact Initial Match ({t1} == {t2})"
                    elif t1_clean.startswith(t2_clean) or t2_clean.startswith(t1_clean): conf, expl = 0.95, f"Initial Match ({t1} <-> {t2})"
                    else: conf, expl = 0.0, f"Initial Mismatch ({t1} != {t2})"
                else:
                    res = self.base_matcher.evaluate(t1, t2, use_carlton, use_wikidata, use_jrc, use_l2, strict_unknowns)
                    conf = res['confidence']
                    expl = res['explanation']
                
                if "Structural Gender Mismatch" in expl:
                    global_gender_mismatch = True
                    mismatch_pair = f"{t1} vs {t2}"
                
                total_score += conf
                mapping_details.append(f"({t1}<->{t2}: {conf*100:.0f}%)")
            
            # Final confidence
            if global_gender_mismatch:
                final_confidence = 0.0
                reasoning = f"Compound REJECTED: Global Gender Mismatch detected in strict sequence ({mismatch_pair})."
            else:
                denom = max(N, M) if compound_strategy == "symmetrical" else min(N, M)
                final_confidence = total_score / max(1, denom)
                verdict = "Approved" if final_confidence >= 0.8 else ("Dubious" if final_confidence > 0.2 else "Rejected")
                reasoning = f"Compound STRICT ORDER [{verdict}]: " + ", ".join(mapping_details)
                if N != M and compound_strategy == "asymmetrical":
                    reasoning += f" (Truncated {abs(N-M)} extra tokens)"

            return {
                "name1": name1, "name2": name2,
                "match": bool(final_confidence >= 0.8),
                "confidence": float(round(final_confidence, 4)),
                "explanation": reasoning
            }
            
        # Build the N x M similarity matrix (Only reaches here if strict_order is False)
        matrix = []
        explanations_matrix = []
        for t1 in tokens1:
            row = []
            exp_row = []
            for t2 in tokens2:
                # --- Initials Evaluator ---
                t1_clean = t1.lower()
                t2_clean = t2.lower()
                is_initial_t1 = len(t1_clean) == 1
                is_initial_t2 = len(t2_clean) == 1
                
                if (is_initial_t1 or is_initial_t2) and not allow_initials:
                    row.append(0.0)
                    exp_row.append(f"Initials Disallowed ({t1} <-> {t2})")
                elif is_initial_t1 and not is_initial_t2:
                    if t2_clean.startswith(t1_clean):
                        row.append(0.95)
                        exp_row.append(f"Initial Match ({t1} -> {t2})")
                    else:
                        row.append(0.0)
                        exp_row.append(f"Initial Mismatch ({t1} != {t2})")
                elif is_initial_t2 and not is_initial_t1:
                    if t1_clean.startswith(t2_clean):
                        row.append(0.95)
                        exp_row.append(f"Initial Match ({t2} -> {t1})")
                    else:
                        row.append(0.0)
                        exp_row.append(f"Initial Mismatch ({t2} != {t1})")
                elif is_initial_t1 and is_initial_t2:
                    if t1_clean == t2_clean:
                        row.append(1.0)
                        exp_row.append(f"Exact Initial Match ({t1} == {t2})")
                    else:
                        row.append(0.0)
                        exp_row.append(f"Initial Mismatch ({t1} != {t2})")
                else:
                    # Normal multi-character evaluation
                    res = self.base_matcher.evaluate(t1, t2, use_carlton, use_wikidata, use_jrc, use_l2, strict_unknowns)
                    row.append(res['confidence'])
                    exp_row.append(res['explanation'])
            matrix.append(row)
            explanations_matrix.append(exp_row)
            
        # Find optimal bipartite assignment
        # Since name tokens are small (usually <= 4), we can just brute force permutations of the smaller set to find the optimal index mapping.
        if N <= M:
            indices_A = list(range(N))
            items_B = list(range(M))
        else:
            indices_A = list(range(M))
            items_B = list(range(N))
            
        # Test all permutations mapping the smaller token list to a subset of the larger token list
        best_score = -1.0
        best_mapping = None
        global_gender_mismatch = False
        mismatch_pair = ""

        for perm in itertools.permutations(items_B, len(indices_A)):
            current_score = 0.0
            current_mapping = []
            perm_gender_mismatch = False
            perm_mismatch_pair = ""
            
            for i, mapped_b_idx in enumerate(perm):
                if N <= M:
                    t1_idx = indices_A[i]
                    t2_idx = mapped_b_idx
                else:
                    t1_idx = mapped_b_idx
                    t2_idx = indices_A[i]
                
                conf = matrix[t1_idx][t2_idx]
                expl = explanations_matrix[t1_idx][t2_idx]
                
                # Check for categorical gender veto from base matcher
                if "Structural Gender Mismatch" in expl:
                    perm_gender_mismatch = True
                    perm_mismatch_pair = f"{tokens1[t1_idx]} vs {tokens2[t2_idx]}"
                
                current_score += conf
                current_mapping.append((t1_idx, t2_idx))
                
            if current_score > best_score:
                best_score = current_score
                best_mapping = current_mapping
                global_gender_mismatch = perm_gender_mismatch
                mismatch_pair = perm_mismatch_pair
                
        # Calculate final average confidence
        if global_gender_mismatch:
            final_confidence = 0.0
        elif compound_strategy == "asymmetrical":
            final_confidence = best_score / max(1, min(N, M))
        else:
            final_confidence = best_score / max(1, max(N, M))
            
        # Construct summary explanation
        if global_gender_mismatch:
            reasoning = f"Compound REJECTED: Global Gender Mismatch detected in component pair ({mismatch_pair}). Instant categorical veto applied to entire entity."
            is_match = False
        else:
            is_match = bool(final_confidence >= 0.8)
            mapping_details = []
            for t1_idx, t2_idx in best_mapping:
                conf = matrix[t1_idx][t2_idx]
                mapping_details.append(f"({tokens1[t1_idx]}<->{tokens2[t2_idx]}: {conf*100:.0f}%)")
                
            if final_confidence >= 0.8:
                verdict = "Approved"
            elif final_confidence > 0.2:
                verdict = "Dubious"
            else:
                verdict = "Rejected"
                
            if compound_strategy == "asymmetrical" and N != M:
                ignored_count = abs(N - M)
                reasoning = f"Compound ASYMMETRICAL [{verdict}] (Ignored {ignored_count} extra tokens). Pairs: " + ", ".join(mapping_details)
            else:
                reasoning = f"Compound SYMMETRICAL [{verdict}] (Bipartite optimal alignment): " + ", ".join(mapping_details)
            
        baseline_res = {
            "name1": name1, "name2": name2,
            "match": is_match,
            "confidence": float(round(final_confidence, 4)),
            "explanation": reasoning
        }
        
        # Return best of baseline vs stepwise
        if stepwise_best_res and stepwise_best_res['confidence'] > baseline_res['confidence']:
            stepwise_best_res['name1'] = name1
            stepwise_best_res['name2'] = name2
            return stepwise_best_res
            
        return baseline_res
