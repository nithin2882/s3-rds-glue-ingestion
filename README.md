 Architecture:
                    users.csv
                         |
                         v
                    Amazon S3
                         |
                         v
                  Validation Layer
                         |
                +--------+--------+
                |                 |
                v                 v
          Amazon RDS       S3 Fallback Zone
           (Primary)             |
                                 v
                          AWS Glue Catalog
                                 |
                                 v
                          Replay Process
                                 |
                                 v
                          Amazon RDS