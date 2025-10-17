#!/bin/bash
# Smoke Tests for CerebrOps Post-Deployment Verification

set -e

APP_URL="${APP_URL:-http://localhost:5000}"
MAX_RETRIES=30
RETRY_DELAY=2

echo "🧪 Running CerebrOps Smoke Tests"
echo "Testing URL: $APP_URL"
echo "================================"

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local retries=0
    
    echo "⏳ Waiting for service to be ready..."
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -s -f "$url/health" > /dev/null 2>&1; then
            echo "✅ Service is ready!"
            return 0
        fi
        
        retries=$((retries + 1))
        echo "   Attempt $retries/$MAX_RETRIES..."
        sleep $RETRY_DELAY
    done
    
    echo "❌ Service failed to become ready after $MAX_RETRIES attempts"
    return 1
}

# Test 1: Health Check Endpoint
test_health_check() {
    echo ""
    echo "Test 1: Health Check Endpoint"
    echo "------------------------------"
    
    response=$(curl -s -w "\n%{http_code}" "$APP_URL/health")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ PASS: Health check returned 200"
        echo "   Response: $body"
    else
        echo "❌ FAIL: Health check returned $http_code"
        echo "   Response: $body"
        return 1
    fi
}

# Test 2: Metrics Endpoint
test_metrics_endpoint() {
    echo ""
    echo "Test 2: Metrics Endpoint"
    echo "------------------------"
    
    response=$(curl -s -w "\n%{http_code}" "$APP_URL/metrics")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ PASS: Metrics endpoint returned 200"
    else
        echo "❌ FAIL: Metrics endpoint returned $http_code"
        return 1
    fi
}

# Test 3: Dashboard Endpoint
test_dashboard() {
    echo ""
    echo "Test 3: Dashboard Endpoint"
    echo "--------------------------"
    
    response=$(curl -s -w "\n%{http_code}" "$APP_URL/")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ PASS: Dashboard returned 200"
    else
        echo "❌ FAIL: Dashboard returned $http_code"
        return 1
    fi
}

# Test 4: Logs Endpoint
test_logs_endpoint() {
    echo ""
    echo "Test 4: Logs Endpoint"
    echo "---------------------"
    
    response=$(curl -s -w "\n%{http_code}" "$APP_URL/logs")
    http_code=$(echo "$response" | tail -n 1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ PASS: Logs endpoint returned 200"
    else
        echo "❌ FAIL: Logs endpoint returned $http_code"
        return 1
    fi
}

# Test 5: Pipeline Status Endpoint
test_pipeline_status() {
    echo ""
    echo "Test 5: Pipeline Status Endpoint"
    echo "---------------------------------"
    
    response=$(curl -s -w "\n%{http_code}" "$APP_URL/pipeline-status")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ PASS: Pipeline status returned 200"
        # Check if response is valid JSON
        if echo "$body" | jq empty 2>/dev/null; then
            echo "   Valid JSON response"
        else
            echo "⚠️  WARNING: Response is not valid JSON"
        fi
    else
        echo "❌ FAIL: Pipeline status returned $http_code"
        return 1
    fi
}

# Test 6: Response Time Check
test_response_time() {
    echo ""
    echo "Test 6: Response Time Check"
    echo "---------------------------"
    
    response_time=$(curl -s -w "%{time_total}" -o /dev/null "$APP_URL/health")
    
    # Convert to milliseconds
    response_time_ms=$(echo "$response_time * 1000" | bc)
    
    echo "   Response time: ${response_time_ms}ms"
    
    # Check if response time is under 2 seconds
    if (( $(echo "$response_time < 2.0" | bc -l) )); then
        echo "✅ PASS: Response time is acceptable"
    else
        echo "⚠️  WARNING: Response time is slow (>${response_time_ms}ms)"
    fi
}

# Main test execution
main() {
    wait_for_service "$APP_URL" || exit 1
    
    failed_tests=0
    
    test_health_check || failed_tests=$((failed_tests + 1))
    test_metrics_endpoint || failed_tests=$((failed_tests + 1))
    test_dashboard || failed_tests=$((failed_tests + 1))
    test_logs_endpoint || failed_tests=$((failed_tests + 1))
    test_pipeline_status || failed_tests=$((failed_tests + 1))
    test_response_time
    
    echo ""
    echo "================================"
    if [ $failed_tests -eq 0 ]; then
        echo "✅ All smoke tests passed!"
        echo "================================"
        exit 0
    else
        echo "❌ $failed_tests test(s) failed"
        echo "================================"
        exit 1
    fi
}

main
