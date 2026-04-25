
output "sagemaker_endpoint_name" {
  description = "Name of the SageMaker endpoint"
  value       = aws_sagemaker_endpoint.embedding_endpoint.name
}

output "sagemaker_endpoint_arn" {
  description = "ARN of the SageMaker endpoint"
  value       = aws_sagemaker_endpoint.embedding_endpoint.arn
}

output "setup_instructions" {
  description = "Instructions for setting up environment variables"
  value = <<-EOT
    
    ✅ SageMaker endpoint deployed successfully!
    
    Add the following to your .env file:
    SAGEMAKER_ENDPOINT=${aws_sagemaker_endpoint.embedding_endpoint.name}

    Test the endpoint:
    Navigate to backend directory where test payload is located
    > cd ../../backend

    Invoke the endpoint and output directly to console
    > aws sagemaker-runtime invoke-endpoint --endpoint-name ${aws_sagemaker_endpoint.embedding_endpoint.name} --content-type application/json --body fileb://vectorize_me.json --output json /dev/stdout
  EOT
}