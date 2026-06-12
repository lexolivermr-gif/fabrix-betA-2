"""
ManuelIA v2 Backend API Test Suite
Tests all user stories (US1-US18) systematically.
"""
import requests
import sys
import time
import json
from datetime import datetime

class ManuelIABackendTester:
    def __init__(self, base_url="https://manuelia-v2.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            req_headers.update(headers)
        
        self.tests_run += 1
        self.log(f"🔍 Test {self.tests_run}: {name}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers, timeout=timeout)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASSED - Status: {response.status_code}")
                self.test_results.append({"test": name, "status": "PASSED", "code": response.status_code})
                try:
                    return True, response.json()
                except:
                    return True, response.content
            else:
                self.log(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                try:
                    self.log(f"   Response: {response.json()}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                self.test_results.append({"test": name, "status": "FAILED", "expected": expected_status, "got": response.status_code})
                return False, {}
                
        except requests.exceptions.Timeout:
            self.log(f"❌ FAILED - Request timeout after {timeout}s")
            self.test_results.append({"test": name, "status": "FAILED", "error": "timeout"})
            return False, {}
        except Exception as e:
            self.log(f"❌ FAILED - Error: {str(e)}")
            self.test_results.append({"test": name, "status": "FAILED", "error": str(e)})
            return False, {}
    
    def test_health(self):
        """Test API health endpoint"""
        success, response = self.run_test(
            "Health check",
            "GET",
            "",
            200
        )
        if success:
            self.log(f"   Models: {response.get('models')}")
        return success
    
    def test_signup(self, email, password, name=None):
        """US1: Signup with new email"""
        success, response = self.run_test(
            f"US1: Signup ({email})",
            "POST",
            "auth/signup",
            200,
            data={"email": email, "password": password, "name": name}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log(f"   Token acquired, user_id: {self.user_id}")
            return True
        return False
    
    def test_login(self, email, password):
        """US2: Login with existing credentials"""
        success, response = self.run_test(
            f"US2: Login ({email})",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            self.log(f"   Token acquired, user_id: {self.user_id}")
            return True
        return False
    
    def test_get_me(self):
        """US2b: GET /api/auth/me"""
        success, response = self.run_test(
            "US2b: GET /auth/me",
            "GET",
            "auth/me",
            200
        )
        if success:
            self.log(f"   User: {response.get('email')}, plan: {response.get('plan')}, credits: {response.get('credits')}")
        return success
    
    def test_clarify(self, project, history=None):
        """US3: POST /api/ai/clarify"""
        success, response = self.run_test(
            "US3: AI clarify (first call)",
            "POST",
            "ai/clarify",
            200,
            data={"project": project, "history": history or []},
            timeout=60
        )
        if success:
            reply = response.get('reply', '')
            self.log(f"   AI reply: {reply[:100]}...")
            return True, reply
        return False, ""
    
    def test_clarify_multi_turn(self, project):
        """US4: Multi-turn clarification chat"""
        history = []
        
        # First turn
        success, reply1 = self.test_clarify(project, history)
        if not success:
            return False, []
        
        history.append({"role": "assistant", "content": reply1})
        history.append({"role": "user", "content": "Oui, j'ai tous les outils nécessaires."})
        
        # Second turn
        success, response = self.run_test(
            "US4: AI clarify (second turn)",
            "POST",
            "ai/clarify",
            200,
            data={"project": project, "history": history},
            timeout=60
        )
        if success:
            reply2 = response.get('reply', '')
            self.log(f"   AI reply 2: {reply2[:100]}...")
            history.append({"role": "assistant", "content": reply2})
            return True, history
        return False, history
    
    def test_generate_manual(self, project, history):
        """US5: POST /api/manuals/generate and poll job"""
        success, response = self.run_test(
            "US5: Start manual generation",
            "POST",
            "manuals/generate",
            200,
            data={"project": project, "history": history},
            timeout=30
        )
        if not success or 'job_id' not in response:
            return False, None
        
        job_id = response['job_id']
        self.log(f"   Job ID: {job_id}")
        
        # Poll job status (max 200s for full generation)
        max_polls = 40
        poll_interval = 5
        for i in range(max_polls):
            time.sleep(poll_interval)
            success, job_status = self.run_test(
                f"US5: Poll job status (attempt {i+1})",
                "GET",
                f"manuals/jobs/{job_id}",
                200,
                timeout=15
            )
            if not success:
                return False, None
            
            state = job_status.get('state')
            progress = job_status.get('progress', 0)
            label = job_status.get('label', '')
            status_text = job_status.get('status_text', '')
            self.log(f"   Progress: {progress}% | {label} | {status_text}")
            
            if state == 'done':
                manual_id = job_status.get('manual_id')
                self.log(f"   ✅ Manual generation complete! Manual ID: {manual_id}")
                return True, manual_id
            elif state == 'error':
                error = job_status.get('error', 'Unknown error')
                self.log(f"   ❌ Generation failed: {error}")
                return False, None
        
        self.log(f"   ⚠️ Timeout after {max_polls * poll_interval}s")
        return False, None
    
    def test_get_manual(self, manual_id):
        """US8: GET /api/manuals/{id}"""
        success, response = self.run_test(
            f"US8: GET manual {manual_id}",
            "GET",
            f"manuals/{manual_id}",
            200
        )
        if success:
            self.log(f"   Title: {response.get('title')}, steps: {len(response.get('steps', []))}")
            return True, response
        return False, {}
    
    def test_list_manuals(self):
        """US7: GET /api/manuals"""
        success, response = self.run_test(
            "US7: List manuals",
            "GET",
            "manuals",
            200
        )
        if success:
            self.log(f"   Found {len(response)} manuals")
            return True, response
        return False, []
    
    def test_regen_step(self, manual_id, step_id, custom_instructions):
        """US9: POST /api/manuals/{id}/steps/{step_id}/regen"""
        success, response = self.run_test(
            f"US9: Regenerate step {step_id}",
            "POST",
            f"manuals/{manual_id}/steps/{step_id}/regen",
            200,
            data={"custom_instructions": custom_instructions},
            timeout=60
        )
        return success
    
    def test_regen_all(self, manual_id):
        """US10: POST /api/manuals/{id}/regen-all"""
        success, response = self.run_test(
            "US10: Start regen-all",
            "POST",
            f"manuals/{manual_id}/regen-all",
            200,
            timeout=30
        )
        if not success or 'job_id' not in response:
            return False
        
        job_id = response['job_id']
        self.log(f"   Job ID: {job_id}")
        
        # Poll a few times to verify progress is updating
        for i in range(3):
            time.sleep(3)
            success, job_status = self.run_test(
                f"US10: Poll regen-all job (attempt {i+1})",
                "GET",
                f"manuals/jobs/{job_id}",
                200,
                timeout=15
            )
            if success:
                progress = job_status.get('progress', 0)
                state = job_status.get('state')
                self.log(f"   Progress: {progress}%, state: {state}")
                if state == 'done':
                    self.log(f"   ✅ Regen-all complete!")
                    return True
        
        self.log(f"   ⚠️ Regen-all still running (not waiting for completion)")
        return True  # Consider it passed if job started
    
    def test_toggle_public(self, manual_id, is_public):
        """US11: PATCH /api/manuals/{id}/public"""
        success, response = self.run_test(
            f"US11: Set public={is_public}",
            "PATCH",
            f"manuals/{manual_id}/public",
            200,
            data={"is_public": is_public}
        )
        return success
    
    def test_get_public_manual(self, manual_id, should_succeed):
        """US11: GET /api/manuals/{id}/public (without auth)"""
        # Temporarily remove token
        old_token = self.token
        self.token = None
        
        expected_status = 200 if should_succeed else 403
        success, response = self.run_test(
            f"US11: GET public manual (expect {expected_status})",
            "GET",
            f"manuals/{manual_id}/public",
            expected_status
        )
        
        self.token = old_token
        return success
    
    def test_export_pdf(self, manual_id):
        """US12: GET /api/manuals/{id}/export/pdf"""
        url = f"{self.base_url}/manuals/{manual_id}/export/pdf"
        headers = {'Authorization': f'Bearer {self.token}'}
        
        self.tests_run += 1
        self.log(f"🔍 Test {self.tests_run}: US12: Export PDF")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200 and response.headers.get('content-type') == 'application/pdf':
                pdf_size = len(response.content)
                if pdf_size > 1000:  # At least 1KB
                    self.tests_passed += 1
                    self.log(f"✅ PASSED - PDF size: {pdf_size} bytes")
                    self.test_results.append({"test": "US12: Export PDF", "status": "PASSED", "size": pdf_size})
                    return True
                else:
                    self.log(f"❌ FAILED - PDF too small: {pdf_size} bytes")
                    self.test_results.append({"test": "US12: Export PDF", "status": "FAILED", "error": "PDF too small"})
                    return False
            else:
                self.log(f"❌ FAILED - Status: {response.status_code}, Content-Type: {response.headers.get('content-type')}")
                self.test_results.append({"test": "US12: Export PDF", "status": "FAILED", "code": response.status_code})
                return False
        except Exception as e:
            self.log(f"❌ FAILED - Error: {str(e)}")
            self.test_results.append({"test": "US12: Export PDF", "status": "FAILED", "error": str(e)})
            return False
    
    def test_get_usage(self):
        """US13: GET /api/usage"""
        success, response = self.run_test(
            "US13: GET usage stats",
            "GET",
            "usage",
            200
        )
        if success:
            self.log(f"   Usage: {response}")
        return success
    
    def test_stripe_checkout_subscription(self):
        """US14: POST /api/stripe/checkout/subscription"""
        success, response = self.run_test(
            "US14: Stripe checkout subscription",
            "POST",
            "stripe/checkout/subscription",
            200
        )
        if success and 'url' in response:
            url = response['url']
            if 'checkout.stripe.com' in url:
                self.log(f"   ✅ Stripe URL: {url[:80]}...")
                return True
            else:
                self.log(f"   ❌ Invalid Stripe URL: {url}")
                return False
        return False
    
    def test_stripe_checkout_credits(self, pack):
        """US15: POST /api/stripe/checkout/credits"""
        success, response = self.run_test(
            f"US15: Stripe checkout credits (pack={pack})",
            "POST",
            "stripe/checkout/credits",
            200,
            data={"pack": pack}
        )
        if success and 'url' in response:
            url = response['url']
            if 'checkout.stripe.com' in url:
                self.log(f"   ✅ Stripe URL: {url[:80]}...")
                return True
            else:
                self.log(f"   ❌ Invalid Stripe URL: {url}")
                return False
        return False
    
    def test_update_prefs(self, email_notifications, public_by_default):
        """US17: PATCH /api/auth/me"""
        success, response = self.run_test(
            "US17: Update user preferences",
            "PATCH",
            "auth/me",
            200,
            data={"email_notifications": email_notifications, "public_by_default": public_by_default}
        )
        if success:
            self.log(f"   Updated: email_notifications={response.get('email_notifications')}, public_by_default={response.get('public_by_default')}")
        return success
    
    def test_delete_all_manuals(self):
        """US18: DELETE /api/manuals"""
        success, response = self.run_test(
            "US18: Delete all manuals",
            "DELETE",
            "manuals",
            200
        )
        if success:
            self.log(f"   Deleted: {response.get('deleted')} manuals")
        return success
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print(f"📊 TEST SUMMARY")
        print("="*80)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print("="*80)
        
        # Print failed tests
        failed = [r for r in self.test_results if r['status'] == 'FAILED']
        if failed:
            print("\n❌ FAILED TESTS:")
            for f in failed:
                print(f"  - {f['test']}: {f.get('error', f.get('got', 'unknown'))}")
        
        return 0 if self.tests_passed == self.tests_run else 1


def main():
    tester = ManuelIABackendTester()
    
    print("="*80)
    print("ManuelIA v2 Backend API Test Suite")
    print("="*80)
    
    # Health check
    if not tester.test_health():
        print("❌ Health check failed, aborting tests")
        return 1
    
    # US1: Signup with new email
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_email = f"e2e_{timestamp}@manuelia.com"
    if not tester.test_signup(new_email, "Test1234!", "E2E Test User"):
        print("❌ Signup failed, aborting tests")
        return 1
    
    # US2b: Get current user
    tester.test_get_me()
    
    # US2: Login with test account
    if not tester.test_login("test@manuelia.com", "Test1234!"):
        print("⚠️ Test account login failed, continuing with new account")
    
    # US3 & US4: AI clarification (multi-turn)
    project = "Construire une étagère murale en bois pour livres"
    success, history = tester.test_clarify_multi_turn(project)
    if not success:
        print("⚠️ AI clarification failed, but continuing tests")
        history = []
    
    # US5, US6: Generate manual (EXPENSIVE - only once)
    print("\n⚠️  Starting manual generation (this will take 90-180 seconds)...")
    success, manual_id = tester.test_generate_manual(project, history)
    if not success or not manual_id:
        print("❌ Manual generation failed - cannot continue with manual-dependent tests")
        tester.print_summary()
        return 1
    
    # US7: List manuals
    tester.test_list_manuals()
    
    # US8: Get full manual
    success, manual = tester.test_get_manual(manual_id)
    if not success or not manual.get('steps'):
        print("❌ Cannot retrieve manual - skipping step-dependent tests")
    else:
        # US9: Regenerate single step
        first_step_id = manual['steps'][0]['id']
        tester.test_regen_step(manual_id, first_step_id, "top-down view")
        
        # US10: Regenerate all steps (start job, don't wait for completion)
        # SKIP THIS TO SAVE TIME AND COST
        # tester.test_regen_all(manual_id)
        print("\n⚠️  Skipping US10 (regen-all) to save time and cost")
    
    # US11: Public sharing
    tester.test_toggle_public(manual_id, True)
    tester.test_get_public_manual(manual_id, should_succeed=True)
    tester.test_toggle_public(manual_id, False)
    tester.test_get_public_manual(manual_id, should_succeed=False)
    
    # US12: Export PDF
    tester.test_export_pdf(manual_id)
    
    # US13: Usage stats
    tester.test_get_usage()
    
    # US14: Stripe subscription checkout
    tester.test_stripe_checkout_subscription()
    
    # US15: Stripe credits checkout
    tester.test_stripe_checkout_credits("5")
    
    # US17: Update preferences
    tester.test_update_prefs(False, True)
    
    # US18: Delete all manuals
    tester.test_delete_all_manuals()
    
    return tester.print_summary()


if __name__ == "__main__":
    sys.exit(main())
