from fastapi.testclient import TestClient


class TestHealthEndpoints:
    def test_health_check_success(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_readiness_check_success(self, client: TestClient) -> None:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestStatusEndpoint:
    def test_status_success(self, client: TestClient, reset_app_state) -> None:
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "operational"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data
        assert data["request_count"] > 0
        assert data["uptime_seconds"] >= 0
    
    def test_status_response_structure(self, client: TestClient, reset_app_state) -> None:
        response = client.get("/status")
        data = response.json()
        
        required_fields = [
            "status", "environment", "version", "timestamp",
            "request_count", "uptime_seconds"
        ]
        for field in required_fields:
            assert field in data
    
    def test_status_request_count_increments(self, client: TestClient, reset_app_state) -> None:
        response1 = client.get("/status")
        count1 = response1.json()["request_count"]
        
        response2 = client.get("/status")
        count2 = response2.json()["request_count"]
        
        assert count2 > count1


class TestDataEndpoint:
    def test_post_data_success(self, client: TestClient, reset_app_state) -> None:
        payload = {"message": "test", "data": {"key": "value"}}
        response = client.post("/data", json=payload)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["id"] == 1
        assert "timestamp" in data
    
    def test_post_data_empty_payload(self, client: TestClient, reset_app_state) -> None:
        response = client.post("/data", json={})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["id"] == 1
    
    def test_post_data_with_message_only(self, client: TestClient, reset_app_state) -> None:
        payload = {"message": "hello world"}
        response = client.post("/data", json=payload)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
    
    def test_post_data_with_data_only(self, client: TestClient, reset_app_state) -> None:
        payload = {"data": {"nested": {"key": "value"}}}
        response = client.post("/data", json=payload)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
    
    def test_post_data_increments_id(self, client: TestClient, reset_app_state) -> None:
        payload = {"message": "test"}
        
        response1 = client.post("/data", json=payload)
        id1 = response1.json()["id"]
        
        response2 = client.post("/data", json=payload)
        id2 = response2.json()["id"]
        
        assert id2 == id1 + 1
    
    def test_post_data_multiple_entries(self, client: TestClient, reset_app_state) -> None:
        payload = {"message": "entry"}
        
        ids = []
        for i in range(5):
            response = client.post("/data", json=payload)
            assert response.status_code == 202
            ids.append(response.json()["id"])
        
        assert ids == [1, 2, 3, 4, 5]


class TestMetricsEndpoint:
    def test_metrics_success(self, client: TestClient, reset_app_state) -> None:
        response = client.get("/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "request_count" in data
        assert "stored_data_count" in data
        assert "uptime_seconds" in data
    
    def test_metrics_data_count(self, client: TestClient, reset_app_state) -> None:
        for i in range(3):
            client.post("/data", json={"message": f"test {i}"})
        
        response = client.get("/metrics")
        data = response.json()
        assert data["stored_data_count"] == 3
    
    def test_metrics_response_structure(self, client: TestClient, reset_app_state) -> None:
        response = client.get("/metrics")
        data = response.json()
        
        required_fields = [
            "request_count", "stored_data_count", "uptime_seconds",
            "environment", "version", "timestamp"
        ]
        for field in required_fields:
            assert field in data


class TestIntegration:
    def test_workflow_sequence(self, client: TestClient, reset_app_state) -> None:
        health = client.get("/health")
        assert health.status_code == 200
        
        status1 = client.get("/status")
        assert status1.status_code == 200
        initial_count = status1.json()["request_count"]
        
        data_response = client.post(
            "/data",
            json={"message": "integration test", "data": {"test": True}}
        )
        assert data_response.status_code == 202
        
        status2 = client.get("/status")
        assert status2.status_code == 200
        updated_count = status2.json()["request_count"]
        
        assert updated_count > initial_count
        
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["stored_data_count"] == 1
    
    def test_error_handling_invalid_method(self, client: TestClient) -> None:
        response = client.put("/status")
        assert response.status_code == 405
    
    def test_error_handling_nonexistent_endpoint(self, client: TestClient) -> None:
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestDataValidation:
    def test_post_data_complex_nested_structure(self, client: TestClient, reset_app_state) -> None:
        payload = {
            "message": "complex",
            "data": {
                "level1": {
                    "level2": {
                        "level3": "deep value"
                    },
                    "array": [1, 2, 3],
                    "mix": {
                        "str": "text",
                        "num": 42,
                        "bool": True,
                        "null_val": None
                    }
                }
            }
        }
        response = client.post("/data", json=payload)
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
