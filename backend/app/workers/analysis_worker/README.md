# Analysis Worker

The Analysis Worker is a background process that processes security analysis jobs asynchronously from the main API. It implements the worker pattern from the system architecture, ensuring that long-running analysis tasks don't block API responses.

## Architecture

The worker follows a producer-consumer pattern:

1. **API Layer** (Producer): Creates analysis jobs and publishes them to the queue
2. **Queue Layer** (Message Broker): Redis durable queue for job hand-off
3. **Worker Layer** (Consumer): Claims jobs, executes analyzers, persists results
4. **Storage Layer**: Object storage for asset content retrieval
5. **Database Layer**: PostgreSQL for analysis state and results

## Components

### Core Worker Class

The `AnalysisWorker` class in `worker.py` implements the main worker logic:

- **Job Claiming**: Claims jobs from the queue using the `QueueAdapter`
- **State Management**: Transitions analyses through pending → running → completed/failed
- **Analyzer Execution**: Executes registered analyzers against asset content
- **Error Handling**: Implements retry logic with configurable max retries
- **Timeout Protection**: Prevents stuck jobs with configurable analysis timeout

### Entry Point

The `__main__.py` module provides the standalone entry point for running the worker:

- **Dependency Injection**: Creates and wires up all worker dependencies
- **Configuration**: Loads settings from environment variables
- **Graceful Shutdown**: Handles SIGTERM/SIGINT for clean shutdown
- **Logging**: Configures structured logging for observability

## Configuration

### Environment Variables

The worker requires the following environment variables:

#### Database
- `DATABASE_URL`: PostgreSQL connection string for API role
- `DATABASE_MIGRATION_URL`: PostgreSQL connection string for schema owner role

#### Queue
- `REDIS_URL`: Redis connection string for queue broker

#### Storage
- `S3_ENDPOINT_URL`: S3-compatible endpoint URL
- `S3_ACCESS_KEY`: S3 access key
- `S3_SECRET_KEY`: S3 secret key
- `S3_BUCKET_NAME`: S3 bucket name for asset storage

#### Application
- `ENVIRONMENT`: Environment (development/staging/production)
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR)

#### Worker-Specific
- `WORKER_ANALYSIS_TIMEOUT_SECONDS`: Maximum time per analysis (default: 300)
- `WORKER_MAX_RETRIES`: Maximum retry attempts for failed analyses (default: 3)

### Worker Settings

The `AnalysisWorkerSettings` dataclass configures runtime behavior:

```python
@dataclass(frozen=True)
class AnalysisWorkerSettings:
    analysis_timeout_seconds: float = 300.0  # 5 minutes
    max_retries: int = 3
```

## Running the Worker

### Local Development

#### Using Docker Compose (Recommended)

The worker is included in the Docker Compose configuration:

```bash
# Start all services including worker
docker compose up -d

# View worker logs
docker compose logs -f analysis-worker

# Stop worker
docker compose stop analysis-worker
```

#### Direct Python Execution

For development without Docker:

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://..."
export REDIS_URL="redis://localhost:6379/0"
# ... other environment variables

# Run worker
python -m app.workers.analysis_worker.__main__
```

### Production Deployment

The worker should be deployed as a separate service with:

- **Process Management**: Use systemd, supervisor, or Kubernetes
- **Scaling**: Run multiple worker instances for higher throughput
- **Monitoring**: Track queue depth, processing time, error rates
- **Log Aggregation**: Centralize logs for observability

## Analyzers

Analyzers are pluggable components that perform security analysis on assets. The worker uses an `AnalyzerRegistry` to manage available analyzers.

### Registering Analyzers

Analyzers are registered in the worker entry point:

```python
registry = AnalyzerRegistry()
registry.register(MetadataAnalyzer())
registry.register(SecurityAnalyzer())
# ... more analyzers
```

### Analyzer Interface

All analyzers must implement the `Analyzer` base class:

```python
class Analyzer(ABC):
    @property
    @abstractmethod
    def key(self) -> str:
        """Stable analyzer identity for idempotency."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Analyzer version for idempotency."""
        pass

    @abstractmethod
    async def analyze(
        self,
        asset: DigitalAsset,
        content_stream: AsyncIterator[bytes],
    ) -> AnalysisResult:
        """Analyze asset and return result."""
        pass
```

### Available Analyzers

- **MetadataAnalyzer**: Extracts file metadata (type, size, hash, dimensions)
- **SecurityAnalyzer**: Static analysis for security indicators
- **OCRAnalyzer**: Text extraction from images and PDFs
- **AI Document Analyzer**: AI-powered document analysis

## Job Processing Flow

1. **Claim Job**: Worker claims a job from the queue (FIFO order)
2. **Load Analysis**: Retrieve analysis record from database
3. **Validate State**: Skip if analysis is already in terminal state
4. **Transition to Running**: Update analysis status to "running"
5. **Retrieve Asset**: Fetch digital asset and content from storage
6. **Execute Analyzer**: Run analyzer with asset content stream
7. **Persist Result**: Save analysis result and transition to "completed"
8. **Acknowledge Job**: Remove job from queue
9. **Handle Errors**: On failure, retry or mark as permanently failed

## Error Handling

### Retry Logic

The worker implements exponential backoff for transient failures:

- **Transient Errors**: Storage timeouts, network issues, temporary analyzer failures
- **Permanent Errors**: Invalid asset format, analyzer bugs, configuration errors
- **Retry Limit**: Configurable via `WORKER_MAX_RETRIES`

### Failure States

Analysis can transition to these failure states:

- **failed**: Permanent failure after exceeding max retries
- **cancelled**: Explicit cancellation by user
- **timeout**: Analysis exceeded configured timeout

## Monitoring and Observability

### Metrics to Track

- **Queue Depth**: Number of pending jobs
- **Processing Time**: Average time per analysis
- **Success Rate**: Percentage of successful analyses
- **Error Rate**: Percentage of failed analyses
- **Retry Rate**: Percentage of jobs requiring retries

### Logging

The worker uses structured logging with the following context:

- `analysis_id`: Analysis record identifier
- `analyzer_key`: Analyzer being executed
- `digital_asset_id`: Asset being analyzed
- `status`: Analysis status transitions
- `error`: Error details (sanitized)

### Health Checks

Monitor worker health by checking:

- Queue connectivity (Redis)
- Database connectivity (PostgreSQL)
- Storage connectivity (S3/MinIO)
- Recent job processing success

## Troubleshooting

### Worker Not Processing Jobs

**Symptoms**: Jobs accumulate in queue but worker doesn't process them

**Possible Causes**:
- Worker not running or crashed
- Queue connection issues
- Database connection issues
- Analyzer registration failures

**Debug Steps**:
1. Check worker logs for errors
2. Verify queue connectivity: `redis-cli ping`
3. Verify database connectivity: Check DATABASE_URL
4. Check analyzer registry initialization

### High Failure Rate

**Symptoms**: Many analyses failing with errors

**Possible Causes**:
- Storage connectivity issues
- Analyzer bugs
- Invalid asset formats
- Timeout configuration too low

**Debug Steps**:
1. Check error messages in worker logs
2. Verify storage connectivity and bucket access
3. Test analyzer with sample assets
4. Increase timeout if needed

### Memory Leaks

**Symptoms**: Worker memory usage increases over time

**Possible Causes**:
- Large file buffering in analyzers
- Database connection pool issues
- Queue connection leaks

**Debug Steps**:
1. Monitor memory usage over time
2. Check analyzer memory patterns
3. Verify connection pool configuration
4. Consider worker restart strategy

## Testing

### Unit Tests

Unit tests use mocked dependencies:

```bash
pytest tests/workers/test_analysis_worker.py -v
```

### Integration Tests

Integration tests use real infrastructure:

```bash
# Requires PostgreSQL, Redis, and MinIO running
pytest tests/integration/test_analysis_worker_integration.py -v -m integration
```

## Performance Considerations

### Scaling

- **Horizontal Scaling**: Run multiple worker instances
- **Queue Partitioning**: Use separate queues per analyzer type
- **Connection Pooling**: Configure appropriate pool sizes

### Resource Management

- **Memory**: Monitor for large file handling
- **CPU**: Analyzer execution can be CPU-intensive
- **Network**: Storage download speed impacts processing time

### Optimization

- **Streaming**: Always stream content, never buffer full files
- **Caching**: Cache analyzer results where appropriate
- **Batching**: Process multiple assets when possible

## Security Considerations

- **Secrets Management**: Never log credentials or secrets
- **Input Validation**: Validate all analyzer inputs
- **Sandboxing**: Consider analyzer sandboxing for untrusted code
- **Access Control**: Worker uses least-privilege database role

## References

- **22-Engineering-Backlog E6.T5**: Analysis Worker Implementation
- **03-Architecture §5**: Async Pipeline Architecture
- **02-Domain-Model**: Analysis Entity Invariants
- **08-Security-Architecture**: Worker Security Requirements