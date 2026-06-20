<template>
  <div>
    <n-page-header title="首页" subtitle="查看你的学习统计数据">
      <template #extra>
        <n-space>
          <n-button @click="loadData" :loading="loading">
            <template #icon>
              <n-icon><refresh-outline /></n-icon>
            </template>
            刷新
          </n-button>
        </n-space>
      </template>
    </n-page-header>

    <n-spin :show="loading">
      <n-space vertical size="large" style="margin-top: 24px;">
        <!-- 统计图表区域（桌面 / 平板） -->
        <n-grid v-if="!isMobile" cols="1 s:1 m:3" responsive="screen" :x-gap="16" :y-gap="16">
          <!-- 今日统计 -->
          <n-gi>
            <n-card hoverable size="small">
              <template #header>
                <span class="card-title">
                  <n-icon :size="18" color="#18a058"><calendar-outline /></n-icon>
                  今日统计
                </span>
              </template>
              <div ref="todayChartRef" :style="{ width: '100%', height: chartHeight }"></div>
              <n-divider style="margin: 20px 0;" />
              <n-space vertical size="small" style="text-align: center;">
                <n-statistic label="练习题数" :value="stats.today.total_count">
                  <template #suffix>
                    <n-text style="font-size: 14px;">题</n-text>
                  </template>
                </n-statistic>
                <n-statistic label="正确率">
                  <template #default>
                    <n-text :type="getAccuracyType(stats.today.accuracy)" style="font-size: 24px; font-weight: bold;">
                      {{ stats.today.accuracy }}%
                    </n-text>
                  </template>
                </n-statistic>
              </n-space>
            </n-card>
          </n-gi>

          <!-- 本周统计 -->
          <n-gi>
            <n-card hoverable size="small">
              <template #header>
                <span class="card-title">
                  <n-icon :size="18" color="#2080f0"><bar-chart-outline /></n-icon>
                  本周统计
                </span>
              </template>
              <div ref="weekChartRef" :style="{ width: '100%', height: chartHeight }"></div>
              <n-divider style="margin: 20px 0;" />
              <n-space vertical size="small" style="text-align: center;">
                <n-statistic label="练习题数" :value="stats.week.total_count">
                  <template #suffix>
                    <n-text style="font-size: 14px;">题</n-text>
                  </template>
                </n-statistic>
                <n-statistic label="正确率">
                  <template #default>
                    <n-text :type="getAccuracyType(stats.week.accuracy)" style="font-size: 24px; font-weight: bold;">
                      {{ stats.week.accuracy }}%
                    </n-text>
                  </template>
                </n-statistic>
              </n-space>
            </n-card>
          </n-gi>

          <!-- 全部统计 -->
          <n-gi>
            <n-card hoverable size="small">
              <template #header>
                <span class="card-title">
                  <n-icon :size="18" color="#f0a020"><trending-up-outline /></n-icon>
                  全部统计
                </span>
              </template>
              <div ref="allChartRef" :style="{ width: '100%', height: chartHeight }"></div>
              <n-divider style="margin: 20px 0;" />
              <n-space vertical size="small" style="text-align: center;">
                <n-statistic label="总练习题数" :value="stats.all.total_count">
                  <template #suffix>
                    <n-text style="font-size: 14px;">题</n-text>
                  </template>
                </n-statistic>
                <n-statistic label="总正确率">
                  <template #default>
                    <n-text :type="getAccuracyType(stats.all.accuracy)" style="font-size: 24px; font-weight: bold;">
                      {{ stats.all.accuracy }}%
                    </n-text>
                  </template>
                </n-statistic>
              </n-space>
            </n-card>
          </n-gi>
        </n-grid>

        <!-- 统计卡片（移动端紧凑版） -->
        <div v-if="isMobile" class="m-stats">
          <div
            v-for="card in periodCards"
            :key="card.key"
            class="m-stat-card"
          >
            <div class="m-stat-head">
              <span class="m-stat-title">
                <n-icon :size="17" :color="card.color"><component :is="card.icon" /></n-icon>
                {{ card.title }}
              </span>
              <span class="m-grade" :style="{ color: getGradeColor(card.data.grade) }">
                {{ card.data.grade }}
              </span>
            </div>

            <div class="m-stat-body">
              <!-- 正确率圆环 -->
              <div class="m-ring" :style="ringStyle(card.data)">
                <div class="m-ring-inner">
                  <span class="m-ring-acc" :style="{ color: getGradeColor(card.data.grade) }">
                    {{ card.data.accuracy }}%
                  </span>
                  <span class="m-ring-label">正确率</span>
                </div>
              </div>

              <!-- 数字统计 -->
              <div class="m-nums">
                <div class="m-num">
                  <b>{{ card.data.total_count }}</b>
                  <span>{{ card.key === 'all' ? '总题数' : '题数' }}</span>
                </div>
                <div class="m-num m-num-correct">
                  <b>{{ card.data.correct_count }}</b>
                  <span>正确</span>
                </div>
                <div class="m-num m-num-wrong">
                  <b>{{ card.data.wrong_count }}</b>
                  <span>错误</span>
                </div>
              </div>
            </div>

            <div v-if="card.key === 'all'" class="m-streak">
              <n-icon :size="14"><flame-outline /></n-icon>
              连续学习 {{ stats.consecutive_days }} 天
            </div>
          </div>
        </div>

        <!-- 等级说明 -->
        <n-card>
          <template #header>
            <span class="card-title">
              <n-icon :size="18" color="#18a058"><document-text-outline /></n-icon>
              等级评价标准
            </span>
          </template>
          <n-space>
            <n-tag type="success">A: ≥90%</n-tag>
            <n-tag type="info">B: 80-89%</n-tag>
            <n-tag type="warning">C: 70-79%</n-tag>
            <n-tag type="warning">D: 60-69%</n-tag>
            <n-tag type="error">F: <60%</n-tag>
          </n-space>
        </n-card>

        <!-- 使用教程 -->
        <n-card hoverable>
          <template #header>
            <span class="card-title">
              <n-icon :size="18" color="#2080f0"><library-outline /></n-icon>
              使用教程
            </span>
          </template>
          <n-collapse>
            <n-collapse-item name="0">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><home-outline /></n-icon>首页统计</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">✨ 一目了然的学习数据可视化</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text>• <n-text strong>今日统计</n-text>：查看今天的练习情况，圆环图中心显示今日等级</n-text>
                <n-text>• <n-text strong>本周统计</n-text>：了解本周整体学习进度，追踪周目标</n-text>
                <n-text>• <n-text strong>全部统计</n-text>：查看累计学习成果，中心显示总体等级和连续学习天数</n-text>
                <n-text>• <n-text strong>等级评价</n-text>：A（优秀）≥90%、B（良好）80-89%、C/D（及格）60-79%、F（不及格）<60%</n-text>
                <n-text depth="3">💡 提示：每天登录练习可累积连续学习天数，坚持就是胜利！</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="1">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><book-outline /></n-icon>科目管理</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">📚 创建和管理你的学习科目</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text>• 在「科目管理」页面，点击「添加科目」按钮创建新科目</n-text>
                <n-text>• 输入科目名称（如：高等数学、大学物理、计算机网络等）</n-text>
                <n-text>• 每个科目独立管理题目、练习记录和错题集</n-text>
                <n-text>• 支持编辑科目名称，随时调整分类</n-text>
                <n-text>• 删除科目会同时删除该科目下的所有题目和记录，请谨慎操作</n-text>
                <n-text depth="3">💡 建议：按课程或章节创建科目，便于针对性复习</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="2">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><cloud-upload-outline /></n-icon>导入题目（AI智能识别）</span>
              </template>
              <n-space vertical>
                <n-text strong type="success">✨ 核心功能：利用 AI 视觉模型直接识别图片中的题目</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📸 图片要求：</n-text>
                <n-text>• 支持格式：JPG、PNG、JPEG、BMP、WEBP</n-text>
                <n-text>• 建议使用高清图片，确保文字清晰可读</n-text>
                <n-text>• 避免图片过暗、模糊或有反光</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🎯 识别流程：</n-text>
                <n-text>1. 在「导入题目」页面选择目标科目</n-text>
                <n-text>2. 点击上传区域或拖拽图片到上传框</n-text>
                <n-text>3. AI 自动识别题目类型（单选/多选/判断/填空）</n-text>
                <n-text>4. 自动提取题干、选项、答案和解析</n-text>
                <n-text>5. 预览识别结果，可手动编辑修正</n-text>
                <n-text>6. 确认无误后点击「导入」保存到题库</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>⚙️ 配置要求：</n-text>
                <n-text>• 首次使用需在「AI 模型配置」中设置 OpenAI API Key</n-text>
                <n-text>• 支持自定义 API 基础 URL，兼容第三方 API 服务</n-text>
                <n-text depth="3">💡 小技巧：批量识别时建议每张图片只包含 1-3 道题，识别准确率更高</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="3">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><library-outline /></n-icon>题库管理</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">📖 浏览和管理题库内容</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🔍 筛选功能：</n-text>
                <n-text>• 按科目筛选：快速定位某个科目的所有题目</n-text>
                <n-text>• 按题型筛选：单选、多选、判断、填空分类查看</n-text>
                <n-text>• 关键词搜索：输入题目内容关键词精准查找</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>✏️ 编辑功能：</n-text>
                <n-text>• 点击题目可查看完整内容</n-text>
                <n-text>• 支持编辑题干、选项、答案和解析</n-text>
                <n-text>• 可删除错误或重复的题目</n-text>
                <n-text>• 每页显示 20 道题，支持翻页浏览</n-text>
                <n-text depth="3">💡 提示：定期检查题库，及时修正识别错误的题目</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="4">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><create-outline /></n-icon>开始练习</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">✍️ 开始你的刷题之旅</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🎯 练习流程：</n-text>
                <n-text>1. 在「开始练习」页面选择要练习的科目</n-text>
                <n-text>2. 系统加载该科目下的所有题目</n-text>
                <n-text>3. 所有题目一次性展示，方便通览</n-text>
                <n-text>4. 依次作答，选择你认为正确的答案</n-text>
                <n-text>5. 完成后点击「提交答案」查看成绩</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📋 答题卡功能：</n-text>
                <n-text>• 右侧答题卡实时显示答题进度</n-text>
                <n-text>• 未答题显示灰色，已答题显示绿色</n-text>
                <n-text>• 点击题号快速跳转到对应题目</n-text>
                <n-text>• 提交前确保没有遗漏的题目</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📊 成绩报告：</n-text>
                <n-text>• 系统自动批改，立即显示成绩</n-text>
                <n-text>• 详细展示：总题数、正确题数、错误题数、正确率、等级评定</n-text>
                <n-text>• 错题自动加入错题集，方便后续复习</n-text>
                <n-text>• 练习记录自动保存，可在「做题记录」中查看</n-text>
                <n-text depth="3">💡 建议：认真对待每次练习，养成良好的答题习惯</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="5">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><alert-circle-outline /></n-icon>错题集</span>
              </template>
              <n-space vertical>
                <n-text strong type="error">🔴 重点功能：攻克薄弱环节的利器</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📑 错题展示：</n-text>
                <n-text>• 300px 卡片式布局，每道错题清晰独立展示</n-text>
                <n-text>• 显示题目类型、错误次数和最后错误时间</n-text>
                <n-text>• 正确选项标记为绿色，一目了然</n-text>
                <n-text>• 点击「查看解析」展开答案详解</n-text>
                <n-text>• 支持按科目筛选，针对性复习</n-text>
                <n-text>• 每页显示 12 道错题，可切换 12/24/36/66 条</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>💪 错题练习：</n-text>
                <n-text>• 点击「错题练习」按钮开始专项训练</n-text>
                <n-text>• 只练习错题集中的题目</n-text>
                <n-text>• 答对的题目自动从错题集移除</n-text>
                <n-text>• 重复练习直到完全掌握</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🗑️ 移除功能：</n-text>
                <n-text>• 点击「移除」按钮可手动移除已掌握的错题</n-text>
                <n-text>• 移除后不影响题库中的原题</n-text>
                <n-text depth="3">💡 学习策略：错题本是提分关键，建议每周至少进行 2-3 次错题练习</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="6">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><time-outline /></n-icon>做题记录</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">📝 追踪你的学习轨迹</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📜 记录列表：</n-text>
                <n-text>• 时间倒序排列，最新记录在最前</n-text>
                <n-text>• 每条记录显示：练习时间、科目、题数、正确率、等级</n-text>
                <n-text>• 不同等级用不同颜色标签区分</n-text>
                <n-text>• 支持按科目筛选，查看单科历史成绩</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🔍 查看详情：</n-text>
                <n-text>• 点击「查看详情」按钮展开完整答题情况</n-text>
                <n-text>• 逐题展示：题目内容、你的答案、正确答案、对错标记</n-text>
                <n-text>• 错题显示红色标记，正确题目显示绿色标记</n-text>
                <n-text>• 查看答案解析，理解错误原因</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📈 进步追踪：</n-text>
                <n-text>• 对比不同时间的练习成绩</n-text>
                <n-text>• 观察正确率变化趋势</n-text>
                <n-text>• 分析薄弱知识点</n-text>
                <n-text depth="3">💡 建议：定期回顾做题记录，总结学习经验</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="7">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><trophy-outline /></n-icon>排行榜系统</span>
              </template>
              <n-space vertical>
                <n-text strong type="warning">🏆 激励功能：与他人竞技，激发学习动力</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🌟 六大排行榜：</n-text>
                <n-text>• <n-text strong>综合排行榜</n-text>：查看所有用户的综合排名</n-text>
                <n-text>• <n-text strong>校级排行榜</n-text>：与同校学生比拼</n-text>
                <n-text>• <n-text strong>院级排行榜</n-text>：学院内部竞争</n-text>
                <n-text>• <n-text strong>专业排行榜</n-text>：专业内较量</n-text>
                <n-text>• <n-text strong>班级排行榜</n-text>：班级荣誉争夺</n-text>
                <n-text>• <n-text strong>个人统计</n-text>：查看个人在各榜单中的排名</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📊 排名规则：</n-text>
                <n-text>• 综合得分 = 正确题数 + (正确率/100) × 正确题数 × 0.5</n-text>
                <n-text>• 鼓励多练习 + 保持高正确率</n-text>
                <n-text>• 支持时间范围筛选：全部时间、最近 7/30/90 天</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>👤 个人信息完善：</n-text>
                <n-text>• 在「个人中心」完善学校、学院、专业、班级信息</n-text>
                <n-text>• 信息越完整，可查看的排行榜越多</n-text>
                <n-text depth="3">💡 提示：完善个人信息后解锁更多排行榜，与同学良性竞争</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="8">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><document-text-outline /></n-icon>试卷生成</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">📄 智能组卷，模拟考试</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🎲 随机组卷：</n-text>
                <n-text>• 选择科目和题目数量</n-text>
                <n-text>• 系统从题库中随机抽取题目</n-text>
                <n-text>• 支持设置各题型的数量比例</n-text>
                <n-text>• 生成后可预览试卷内容</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>⏱️ 考试模式：</n-text>
                <n-text>• 可设置考试时长，倒计时提醒</n-text>
                <n-text>• 全屏答题，模拟真实考试环境</n-text>
                <n-text>• 时间到自动提交</n-text>
                <n-text>• 查看成绩和试卷分析</n-text>
                <n-text depth="3">💡 建议：考前使用试卷功能进行模拟测试，适应考试节奏</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="9">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><folder-outline /></n-icon>学习资料</span>
              </template>
              <n-space vertical>
                <n-text strong type="primary">📚 课件、笔记、资料管理中心</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📤 上传资料：</n-text>
                <n-text>• 支持上传 PDF、Word、PPT、图片等多种格式</n-text>
                <n-text>• 按科目分类存储</n-text>
                <n-text>• 添加标签方便检索</n-text>
                <n-text>• 支持预览和下载</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🔍 搜索功能：</n-text>
                <n-text>• 按文件名搜索</n-text>
                <n-text>• 按标签筛选</n-text>
                <n-text>• 按上传时间排序</n-text>
                <n-text depth="3">💡 提示：集中管理学习资料，随时随地复习</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="11">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><settings-outline /></n-icon>AI 模型配置</span>
              </template>
              <n-space vertical>
                <n-text strong type="warning">🔑 配置 AI 服务，解锁智能功能</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📝 配置步骤：</n-text>
                <n-text>1. 注册 OpenAI 账号并获取 API Key</n-text>
                <n-text>2. 在「AI 模型配置」页面填入 API Key</n-text>
                <n-text>3. 设置 API 基础 URL（默认使用官方地址）</n-text>
                <n-text>4. 点击「测试连接」验证配置是否正确</n-text>
                <n-text>5. 保存配置后即可使用 AI 功能</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>🌐 自定义 API：</n-text>
                <n-text>• 支持第三方兼容 OpenAI 格式的 API 服务</n-text>
                <n-text>• 可使用国内转发服务，提升访问速度</n-text>
                <n-text>• 修改基础 URL 即可切换服务商</n-text>
                <n-text depth="3">⚠️ 注意：请妥善保管 API Key，避免泄露</n-text>
              </n-space>
            </n-collapse-item>

            <n-collapse-item name="12">
              <template #header>
                <span class="tut-title"><n-icon :size="16"><bulb-outline /></n-icon>高效学习策略</span>
              </template>
              <n-space vertical>
                <n-text strong type="success">🎯 科学方法，事半功倍</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text type="info">1. <n-text strong>定期导入新题</n-text>：保持题库更新，覆盖全部知识点</n-text>
                <n-text type="info">2. <n-text strong>每日坚持练习</n-text>：养成习惯，查看首页统计追踪进度</n-text>
                <n-text type="info">3. <n-text strong>重点攻克错题</n-text>：错题是提分关键，至少复习 2-3 遍</n-text>
                <n-text type="info">4. <n-text strong>利用做题记录</n-text>：分析进步趋势，找出薄弱环节</n-text>
                <n-text type="info">5. <n-text strong>参与排行榜</n-text>：与同学良性竞争，激发学习动力</n-text>
                <n-text type="info">6. <n-text strong>模拟考试</n-text>：定期使用试卷功能进行全真模拟</n-text>
                <n-text type="info">7. <n-text strong>合理使用 AI</n-text>：遇到问题及时请教，深入理解知识点</n-text>
                <n-text type="info">8. <n-text strong>目标设定</n-text>：争取达到 A 级（正确率 ≥90%），确保知识掌握扎实</n-text>
                <n-divider style="margin: 8px 0;" />
                <n-text strong>📅 推荐学习计划：</n-text>
                <n-text>• 每天练习 30-60 分钟</n-text>
                <n-text>• 每周错题复习 2-3 次</n-text>
                <n-text>• 每月模拟考试 1-2 次</n-text>
                <n-text>• 定期查看学习统计，调整学习策略</n-text>
              </n-space>
            </n-collapse-item>
          </n-collapse>
        </n-card>
      </n-space>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { practiceApi } from '@/api'
import { RefreshOutline, CalendarOutline, BarChartOutline, TrendingUpOutline, DocumentTextOutline, LibraryOutline, FlameOutline, HomeOutline, BookOutline, CloudUploadOutline, CreateOutline, AlertCircleOutline, TimeOutline, TrophyOutline, FolderOutline, SettingsOutline, BulbOutline } from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import * as echarts from 'echarts'
import { useBreakpoint } from '@/composables/useBreakpoint'

const message = useMessage()
const loading = ref(false)
const userStore = useUserStore()
const { userId } = storeToRefs(userStore)

// 响应式：移动端图表高度略降，避免堆叠后过高
const { isMobile, width } = useBreakpoint()
const chartHeight = computed(() => (isMobile.value ? '300px' : '350px'))

// ECharts 实例引用
const todayChartRef = ref(null)
const weekChartRef = ref(null)
const allChartRef = ref(null)
let todayChart = null
let weekChart = null
let allChart = null

const stats = ref({
  today: {
    total_count: 0,
    correct_count: 0,
    wrong_count: 0,
    accuracy: 0,
    grade: 'F'
  },
  week: {
    total_count: 0,
    correct_count: 0,
    wrong_count: 0,
    accuracy: 0,
    grade: 'F'
  },
  all: {
    total_count: 0,
    correct_count: 0,
    wrong_count: 0,
    accuracy: 0,
    grade: 'F'
  },
  consecutive_days: 0
})

// 获取正确率颜色类型
const getAccuracyType = (accuracy) => {
  if (accuracy >= 90) return 'success'
  if (accuracy >= 80) return 'info'
  if (accuracy >= 70) return 'warning'
  return 'error'
}

// 获取等级颜色类型
const getGradeType = (grade) => {
  if (grade === 'A') return 'success'
  if (grade === 'B') return 'info'
  if (grade === 'C' || grade === 'D') return 'warning'
  return 'error'
}

// 获取等级颜色（用于图表）
const getGradeColor = (grade) => {
  if (grade === 'A') return '#18a058'
  if (grade === 'B') return '#2080f0'
  if (grade === 'C' || grade === 'D') return '#f0a020'
  return '#d03050'
}

// 移动端紧凑统计卡片数据
const periodCards = computed(() => [
  { key: 'today', title: '今日统计', icon: CalendarOutline, color: '#18a058', data: stats.value.today },
  { key: 'week', title: '本周统计', icon: BarChartOutline, color: '#2080f0', data: stats.value.week },
  { key: 'all', title: '全部统计', icon: TrendingUpOutline, color: '#f0a020', data: stats.value.all }
])

// 移动端圆环：用 conic-gradient 表示正确率占比
const ringStyle = (data) => {
  const total = (data.correct_count || 0) + (data.wrong_count || 0)
  const acc = total > 0 ? (data.correct_count / total) * 100 : 0
  return {
    background: `conic-gradient(#18a058 0% ${acc}%, #d03050 ${acc}% 100%)`
  }
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const data = await practiceApi.homeStats(userId.value)
    stats.value = data
    // 等待 DOM 更新后初始化图表
    await nextTick()
    initCharts()
  } catch (error) {
    message.error(error.message || '加载统计数据失败')
  } finally {
    loading.value = false
  }
}

// 初始化所有图表
const initCharts = () => {
  // 移动端使用紧凑卡片，不渲染 ECharts
  if (isMobile.value) return
  initTodayChart()
  initWeekChart()
  initAllChart()
}

// 初始化今日统计图表
const initTodayChart = () => {
  if (!todayChartRef.value) return
  
  if (todayChart) {
    todayChart.dispose()
  }
  
  todayChart = echarts.init(todayChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 题 ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: '5%',
      left: 'center',
      itemGap: 20,
      textStyle: {
        fontSize: 14
      }
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: stats.value.today.grade,
          fontSize: 48,
          fontWeight: 'bold',
          fill: getGradeColor(stats.value.today.grade)
        }
      }
    ],
    series: [
      {
        name: '今日统计',
        type: 'pie',
        radius: ['45%', '68%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 3
        },
        label: {
          show: true,
          position: 'outside',
          fontSize: 14,
          fontWeight: 'bold',
          formatter: '{c} 题'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        data: [
          { 
            value: stats.value.today.correct_count, 
            name: '正确题数',
            itemStyle: { color: '#18a058' }
          },
          { 
            value: stats.value.today.wrong_count, 
            name: '错误题数',
            itemStyle: { color: '#d03050' }
          }
        ]
      }
    ]
  }
  
  todayChart.setOption(option)
}

// 初始化本周统计图表
const initWeekChart = () => {
  if (!weekChartRef.value) return
  
  if (weekChart) {
    weekChart.dispose()
  }
  
  weekChart = echarts.init(weekChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 题 ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: '5%',
      left: 'center',
      itemGap: 20,
      textStyle: {
        fontSize: 14
      }
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: 'center',
        style: {
          text: stats.value.week.grade,
          fontSize: 48,
          fontWeight: 'bold',
          fill: getGradeColor(stats.value.week.grade)
        }
      }
    ],
    series: [
      {
        name: '本周统计',
        type: 'pie',
        radius: ['45%', '68%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 3
        },
        label: {
          show: true,
          position: 'outside',
          fontSize: 14,
          fontWeight: 'bold',
          formatter: '{c} 题'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        data: [
          { 
            value: stats.value.week.correct_count, 
            name: '正确题数',
            itemStyle: { color: '#18a058' }
          },
          { 
            value: stats.value.week.wrong_count, 
            name: '错误题数',
            itemStyle: { color: '#d03050' }
          }
        ]
      }
    ]
  }
  
  weekChart.setOption(option)
}

// 初始化全部统计图表
const initAllChart = () => {
  if (!allChartRef.value) return
  
  if (allChart) {
    allChart.dispose()
  }
  
  allChart = echarts.init(allChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 题 ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: '5%',
      left: 'center',
      itemGap: 20,
      textStyle: {
        fontSize: 14
      }
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '40%',
        style: {
          text: stats.value.all.grade,
          fontSize: 48,
          fontWeight: 'bold',
          fill: getGradeColor(stats.value.all.grade)
        }
      },
      {
        type: 'text',
        left: 'center',
        top: '53%',
        style: {
          text: `连续 ${stats.value.consecutive_days} 天`,
          fontSize: 16,
          fill: '#999',
          textAlign: 'center'
        }
      }
    ],
    series: [
      {
        name: '全部统计',
        type: 'pie',
        radius: ['45%', '68%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 3
        },
        label: {
          show: true,
          position: 'outside',
          fontSize: 14,
          fontWeight: 'bold',
          formatter: '{c} 题'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        data: [
          { 
            value: stats.value.all.correct_count, 
            name: '正确题数',
            itemStyle: { color: '#18a058' }
          },
          { 
            value: stats.value.all.wrong_count, 
            name: '错误题数',
            itemStyle: { color: '#d03050' }
          }
        ]
      }
    ]
  }
  
  allChart.setOption(option)
}

// 监听窗口大小变化，自动调整图表
const handleResize = () => {
  todayChart?.resize()
  weekChart?.resize()
  allChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

// 桌面 / 移动切换时，切回桌面需要（重新）渲染 ECharts
watch(isMobile, (mobile) => {
  if (!mobile) {
    nextTick(() => initCharts())
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  todayChart?.dispose()
  weekChart?.dispose()
  allChart?.dispose()
})
</script>

<style scoped>
/* 卡片标题（图标 + 文字） */
.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}
.card-title .n-icon {
  position: relative;
  top: 1px;
}

/* 教程折叠面板标题（图标 + 文字） */
.tut-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

/* ============================================================
   移动端紧凑统计卡片
   ============================================================ */
.m-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-stat-card {
  background: #fff;
  border: 1px solid #efefef;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

.m-stat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.m-stat-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.m-grade {
  font-size: 26px;
  font-weight: 900;
  line-height: 1;
  font-family: 'Rajdhani', 'Courier New', monospace;
}

.m-stat-body {
  display: flex;
  align-items: center;
  gap: 18px;
}

/* 正确率圆环（conic-gradient + 中间镂空） */
.m-ring {
  width: 86px;
  height: 86px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-ring-inner {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
}

.m-ring-acc {
  font-size: 17px;
  font-weight: 800;
  line-height: 1.1;
  font-family: 'Rajdhani', 'Courier New', monospace;
}

.m-ring-label {
  font-size: 10px;
  color: #9ca3af;
}

.m-nums {
  flex: 1;
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.m-num {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m-num b {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
  font-family: 'Rajdhani', 'Courier New', monospace;
}

.m-num span {
  font-size: 11px;
  color: #9ca3af;
}

.m-num-correct b {
  color: #18a058;
}

.m-num-wrong b {
  color: #d03050;
}

.m-streak {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: #f0a020;
  background: rgba(240, 160, 32, 0.1);
  border-radius: 8px;
  padding: 7px;
}
</style>
