-- DDL Script: Tạo bảng lưu kết quả Auto-Tagging AI (Pipeline F3.1)
-- Bảng: judge_problem_ai_tag

CREATE TABLE IF NOT EXISTS `judge_problem_ai_tag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `problem_id` int(11) NOT NULL,
  `primary_tag_id` int(11) NOT NULL,
  `secondary_tag_ids` json DEFAULT NULL,
  `bloom_group_id` int(11) DEFAULT NULL,
  `reasoning` text DEFAULT NULL,
  `model` varchar(100) NOT NULL DEFAULT 'Qwen3.8-4B-GGUF',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_problem_id` (`problem_id`),
  KEY `idx_primary_tag_id` (`primary_tag_id`),
  KEY `idx_bloom_group_id` (`bloom_group_id`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_problem_ai_tag_problem` FOREIGN KEY (`problem_id`) REFERENCES `judge_problem` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_problem_ai_tag_primary_tag` FOREIGN KEY (`primary_tag_id`) REFERENCES `judge_problemtype` (`id`),
  CONSTRAINT `fk_problem_ai_tag_bloom_group` FOREIGN KEY (`bloom_group_id`) REFERENCES `judge_problemgroup` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
