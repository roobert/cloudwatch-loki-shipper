locals {
  name_prefix_shipper = "ship-"
}

resource "aws_lambda_function" "cloudwatch-loki-shipper" {
  s3_bucket     = "ins-cloudwatch-loki-shipper"
  s3_key        = "cloudwatch-loki-shipper.zip"
  function_name = "cloudwatch-loki-shipper"
  role          = aws_iam_role.cloudwatch-loki-shipper.arn
  handler       = "loki-shipper.lambda_handler"
  memory_size   = "128"
  runtime       = "python3.6"
  timeout       = "600"
  environment {
    variables = {
      LOKI_ENDPOINT          = "http://metrics.example.com:3100"
      LOG_LABELS             = "classname,logger_name"
      LOG_TEMPLATE           = "level=$level | $message"
      LOG_TEMPLATE_VARIABLES = "level,message"
      LOG_IGNORE_NON_JSON    = "true"
    }
  }
  vpc_config {
    subnet_ids         = module.vpc.public_subnets
    security_group_ids = [module.in-out-all.this_security_group_id]
  }
}

resource "aws_lambda_permission" "cloudwatch-loki-shipper" {
  statement_id  = "cloudwatch-loki-shipper"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cloudwatch-loki-shipper.arn
  principal     = "logs.${var.region}.amazonaws.com"
  source_arn    = aws_cloudwatch_log_group.events-router.arn
}

resource "aws_cloudwatch_log_subscription_filter" "cloudwatch-loki-shipper" {
  depends_on      = [aws_lambda_permission.cloudwatch-loki-shipper]
  name            = "cloudwatch-loki-shipper"
  log_group_name  = aws_cloudwatch_log_group.events-router.name
  filter_pattern  = ""
  destination_arn = aws_lambda_function.cloudwatch-loki-shipper.arn
}

resource "aws_cloudwatch_log_group" "cloudwatch-loki-shipper" {
  name              = "/aws/lambda/cloudwatch-loki-shipper"
  retention_in_days = 1
}

resource "aws_iam_role_policy_attachment" "cloudwatch-loki-shipper" {
  role       = aws_iam_role.cloudwatch-loki-shipper.name
  policy_arn = aws_iam_policy.cloudwatch-loki-shipper.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch-loki-shipper-vpc-policy" {
  role       = aws_iam_role.cloudwatch-loki-shipper.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role" "cloudwatch-loki-shipper" {
  name_prefix = local.name_prefix_shipper

  assume_role_policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": "sts:AssumeRole",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Effect": "Allow",
          "Sid": ""
        }
      ]
    }
  EOF
}

resource "aws_iam_policy" "cloudwatch-loki-shipper" {
  name_prefix = local.name_prefix_shipper

  policy = <<-EOF
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Action": [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:*",
            "logs:PutLogEvents"
          ],
          "Resource": "arn:aws:logs:*:*:*",
          "Effect": "Allow"
        },
        {
          "Action": [
            "ec2:DescribeNetworkInterfaces",
            "ec2:CreateNetworkInterface",
            "ec2:DeleteNetworkInterface"
          ],
          "Resource": "*",
          "Effect": "Allow"
        }
      ]
    }
  EOF
}

