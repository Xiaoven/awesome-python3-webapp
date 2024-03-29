drop database if exists awesome;

create database awesome;

use awesome;

--mysql 8
create user if not exists 'www-data'@'localhost' identified by 'www-data';
grant select, insert, update, delete on awesome.* to 'www-data'@'localhost' with grant option;
--mysql 5
--grant select, insert, update, delete on awesome.* to 'www-data'@'localhost' identified by 'www-data';

create table users (
   `id` varchar(50) not null,
   `email` varchar(50) not null,
   `passwd` varchar(50) not null,
   `admin` bool not null,
   `name` varchar(50) not null,
   `image` varchar(500) not null,
   `created_at` real not null,
   unique key `idx_email` (`email`),
   key `idx_created_at` (`created_at`),
   primary key (`id`)
) engine=innodb default charset=utf8;

create table blogs (
   `id` varchar(50) not null,
   `user_id` varchar(50) not null,
   `user_name` varchar(50) not null,
   `user_image` varchar(500) not null,
   `name` varchar(50) not null,
   `summary` varchar(200) not null,
   `content` mediumtext not null,
   `created_at` real not null,
   key `idx_created_at` (`created_at`),
   primary key (`id`)
) engine=innodb default charset=utf8;

create table comments (
      `id` varchar(50) not null,
      `blog_id` varchar(50) not null,
      `user_id` varchar(50) not null,
      `user_name` varchar(50) not null,
      `user_image` varchar(500) not null,
      `content` mediumtext not null,
      `created_at` real not null,
      key `idx_created_at` (`created_at`),
      primary key (`id`)
) engine=innodb default charset=utf8;

-- 向 users 插入数据
-- insert into users (id, email, passwd, admin, name, image, created_at) values (2, 'joe@example.com', 'pw', false, 'Joe', 'avatar.png', 110000030);
