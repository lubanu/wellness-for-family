from typing import List, Dict, Any

INCOME_MAP = {
    "under_50": 50,
    "under_100": 100,
    "under_150": 150,
    "under_180": 180,
    "over_180": 999
}

class MatchingEngine:
    @staticmethod
    def match_policy(policy: Dict[str, Any], household: Dict[str, Any]) -> Dict[str, Any]:
        sido = household.get("sido", "seoul")
        sigungu = household.get("sigungu", "gwanak")
        user_region_full = f"{sido}_{sigungu}"
        
        # 1. Region Filtering
        p_region = policy.get("region_code", "ALL")
        if p_region != "ALL" and p_region != user_region_full and p_region != sido:
            return {"is_matched": False, "reason": "REGION_MISMATCH"}
        
        # 2. Income Filtering
        user_income_str = household.get("income_bracket", "under_150")
        user_income_ratio = INCOME_MAP.get(user_income_str, 150)
        eligibility = policy.get("target_eligibility", {})
        limit_ratio = eligibility.get("income_limit_ratio", 999)
        if user_income_ratio > limit_ratio:
            return {"is_matched": False, "reason": "INCOME_EXCEEDED"}
        
        # 3. Age & Member Filtering
        min_age = eligibility.get("min_age", 0)
        max_age = eligibility.get("max_age", 120)
        members = household.get("members", [])
        
        matched_members = []
        if members:
            for m in members:
                age = m.get("age_years", 30)
                if min_age <= age <= max_age:
                    matched_members.append(m)
            # If policy targets specific age cohort and no member fits
            if not matched_members and max_age < 100 and min_age > 0:
                return {"is_matched": False, "reason": "AGE_CRITERIA_UNMET"}
        
        # 4. Tag Filtering
        user_tags = set(household.get("tags", []))
        required_tags = set(eligibility.get("required_tags", []))
        if required_tags and not user_tags.intersection(required_tags):
            return {"is_matched": False, "reason": "TAG_UNMET"}
            
        # 5. Calculation
        certainty = policy.get("certainty_score", 90)
        amount = policy.get("amount_value", 0)
        is_urgent = policy.get("is_urgent", False)
        
        return {
            "is_matched": True,
            "certainty_score": certainty,
            "estimated_amount": amount,
            "is_urgent": is_urgent,
            "matched_members_count": len(matched_members)
        }

    @classmethod
    def evaluate_catalog(cls, policies: List[Dict[str, Any]], household: Dict[str, Any]) -> Dict[str, Any]:
        matched_policies = []
        total_annual = 0
        claimed_annual = 0
        unclaimed_annual = 0
        urgent_count = 0
        
        claimed_ids = set(household.get("claimed_policy_ids", [
            "pol_parent_0", "pol_parent_1", "pol_child_allowance", "pol_first_encounter"
        ]))

        for p in policies:
            eval_res = cls.match_policy(p, household)
            if eval_res["is_matched"]:
                p_copy = dict(p)
                p_copy["certainty"] = eval_res["certainty_score"]
                amt = p.get("amount_value", 0)
                total_annual += amt
                
                is_claimed = p["id"] in claimed_ids
                p_copy["status"] = "CLAIMED" if is_claimed else "UNCLAIMED"
                
                if is_claimed:
                    claimed_annual += amt
                else:
                    unclaimed_annual += amt
                    
                if p.get("is_urgent"):
                    urgent_count += 1
                    
                matched_policies.append(p_copy)
                
        # Sort by urgency and amount
        matched_policies.sort(key=lambda x: (not x.get("is_urgent", False), -x.get("amount_value", 0)))
        
        return {
            "total_annual_amount": total_annual,
            "claimed_annual_amount": claimed_annual,
            "unclaimed_annual_amount": unclaimed_annual,
            "matched_count": len(matched_policies),
            "urgent_dday_count": urgent_count,
            "policies": matched_policies
        }
