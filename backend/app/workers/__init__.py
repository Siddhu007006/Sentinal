"""
Workers subsystem.

Background job consumers that process the asynchronous pipeline
defined in 00-Project-Context.md §5. Workers consume jobs from the
queue, execute logic via the Application/Domain layers, and persist
results through Infrastructure.

Workers never receive HTTP requests and never respond directly to
a browser.

See: 06-Repository-Structure.md §8.
"""
