
#include "dac.h"
#include "main.h"
#include "comp.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"
#include "math.h"
#include "string.h"
#include "stdlib.h"
#include "stdio.h"



float ref_speed  = 0.0f;
float Kp         = 0.0f;
float Ki         = 0.0f;
float integral   = 0.0f;



volatile uint8_t data_ready = 0;

#define FILTER_SIZE  6
float   rpm_buffer[FILTER_SIZE] = {0};
uint8_t rpm_buf_index = 0;
float   rpm_filtered  = 0.0f;
float multiplicator=5;



float f_out = 0.0f;
#define F_NOMINAL  50.0f
#define M_MAX      1.0f
#define MAX_RPM     1700.0f




#define F_CARRIER  5000.0f
#define ARR        4250U
#define TWO_PI     6.2831853f

#define PHASE_120  (TWO_PI / 3.0f)
#define PHASE_240  (TWO_PI * 2.0f / 3.0f)
float current_angle = 0.0f;



#define UART_BUF_SIZE 16
extern UART_HandleTypeDef huart2;



char uart_buf[UART_BUF_SIZE];
uint8_t uart_rx_byte;
uint8_t uart_index = 0;
uint8_t print_counter = 0;
#define TIM2_CLK    170000000.0f



uint32_t capture1        = 0;
uint32_t capture2        = 0;
uint32_t difference      = 0;
uint8_t  first_capture   = 0;
float    frequency       = 0.0f;
float    motor_rpm       = 0.0f;
uint32_t last_capture_time = 0;
char tx_buf[64];


void SystemClock_Config(void);
void syst_initialization(void);
float PI_Controller(float ref, float measured, float dt);
int main(void)
{
	syst_initialization();

  while (1)
  {




	  static uint32_t last_pi_time = 0;

	  if (HAL_GetTick() - last_pi_time >= 1000)
	  {

	      float dt = (HAL_GetTick() - last_pi_time) / 1000.0f;
	      last_pi_time = HAL_GetTick();

	      if (ref_speed > 0.0f)
	      {
	          /* Step 1: run PI, get correction in RPM */
	          float correction = PI_Controller(ref_speed, rpm_filtered, dt);

	          float ws = rpm_filtered + correction;

	          /* Step 3: convert RPM to Hz
	             one rotation per second = 1 Hz
	             60 RPM = 1 rotation per second = 1 Hz */
	          float feedforward = ref_speed * (50.0f / 1440.0f);

	          /* PI correction is small adjustment around feedforward */
	          float new_fout = feedforward + (correction / 60.0f);

	          /* Step 4: clamp to safe range */
	          if (new_fout > 50.0f) new_fout = 50.0f;
	          if (new_fout < 0.0f)  new_fout = 0.0f;
	          //float max_change = f_out * 0.05f;

	          /* Minimum change allowed so it can start from zero */
	          //if (max_change < 0.5f) max_change = 0.5f;


	          //f_out = new_fout;

	          /* Step 5: update f_out — SPWM picks this up automatically */
	          f_out = new_fout;
	      }
	      else
	      {

	    	  rpm_filtered = 0.0f;
	          integral = 0.0f;
	      }
	  }








	    if (data_ready == 1)
	    {
	        data_ready = 0;
	        if (print_counter >= 9)
	        {
	            print_counter = 0;
	            int len = snprintf(tx_buf, sizeof(tx_buf),
	                               "REF:%.0f RPM:%.1f FOUT:%.2f ERR:%.1f\r\n",
	                               ref_speed, rpm_filtered, f_out,
	                               ref_speed - rpm_filtered);
	            HAL_UART_Transmit(&huart2, (uint8_t*)tx_buf, len, 50);
	        }
	    }

	    if (HAL_GetTick() - last_capture_time > 500)
	    {

	    	if (motor_rpm > 0.0f)
	    	{
	    	    motor_rpm    = 0.0f;
	    	    rpm_filtered = 0.0f;
	    	    frequency    = 0.0f;
	    	    first_capture = 0;

	    	    /* Clear filter buffer so next startup begins fresh */
	    	    uint8_t i;
	    	    for (i = 0; i < FILTER_SIZE; i++)
	    	        rpm_buffer[i] = 0.0f;
	    	    rpm_buf_index = 0;

	    	    int len = snprintf(tx_buf, sizeof(tx_buf),
	    	                       "RPM: 0.0 | f_out: %.1f Hz\r\n", f_out);
	    	    HAL_UART_Transmit(&huart2, (uint8_t*)tx_buf, len, 50);
	    	}
	    }
  }
  /* USER CODE END 3 */
}


void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV4;
  RCC_OscInitStruct.PLL.PLLN = 85;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
/* USER CODE BEGIN 4 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART2)
        return;

    /* Echo the character back so you see it in the terminal */
    HAL_UART_Transmit(&huart2, &uart_rx_byte, 1, 10);

    if (uart_rx_byte == '\r' || uart_rx_byte == '\n')
    {
        uart_buf[uart_index] = '\0';

        /* Read the first character — that is the command */
        char  cmd   = uart_buf[0];

        /* Read the number after the command letter */
        float value = atof(&uart_buf[1]);

        if (cmd == 'R' || cmd == 'r')        /* Reference speed in RPM */
        {
            if (value >= 0.0f && value <= 1500.0f)
            {
                ref_speed = value;
                integral  = 0.0f;   /* reset integral on every new setpoint */
            }
        }
        else if (cmd == 'P' || cmd == 'p')   /* Kp gain */
        {
            Kp = value;
        }
        else if (cmd == 'I' || cmd == 'i')   /* Ki gain */
        {
            Ki = value;
        }
        else if (cmd == 'F' || cmd == 'f')   /* manual f_out, open loop still works */
        {
            if (value >= 0.0f && value <= 50.0f)
                f_out = value;
        }

        uart_index = 0;
    }
    else
    {
        if (uart_index < UART_BUF_SIZE - 1)
        {
            uart_buf[uart_index] = uart_rx_byte;
            uart_index++;
        }
    }

      /* Re-arm the interrupt to wait for the next byte */
      HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance != TIM8)
        return;

    if (htim->Instance->CR1 & TIM_CR1_DIR)
        return;

    /* Advance the angle by one step */
    float angle_step = TWO_PI * f_out / F_CARRIER;
    current_angle += angle_step;

    /* Wrap back to zero after one full cycle */
    if (current_angle >= TWO_PI)
        current_angle -= TWO_PI;


    float sin_a = sinf(current_angle);
    float sin_b = sinf(current_angle - PHASE_120);
    float sin_c = sinf(current_angle - PHASE_240);
    float M = M_MAX * (f_out / F_NOMINAL);
    if (M > M_MAX) M = M_MAX;
    /* Convert each sine value into a CCR number (0 to ARR) */
    uint32_t ccr_a = (uint32_t)((ARR / 2.0f) * (1.0f + M * sin_a));
    uint32_t ccr_b = (uint32_t)((ARR / 2.0f) * (1.0f + M * sin_b));
    uint32_t ccr_c = (uint32_t)((ARR / 2.0f) * (1.0f + M * sin_c));

    /* Write duty cycles to all three channels */
    __HAL_TIM_SET_COMPARE(htim, TIM_CHANNEL_1, ccr_a);
    __HAL_TIM_SET_COMPARE(htim, TIM_CHANNEL_2, ccr_b);
    __HAL_TIM_SET_COMPARE(htim, TIM_CHANNEL_3, ccr_c);
}

float RPM_Filter(float new_rpm)
{
    uint8_t i;
    float sum;

    /* If value hit the ceiling it is fake — skip it entirely */
    if (new_rpm >= MAX_RPM)
        return rpm_filtered;

    /* Add real value to buffer */
    rpm_buffer[rpm_buf_index] = new_rpm;
    rpm_buf_index++;
    if (rpm_buf_index >= FILTER_SIZE)
        rpm_buf_index = 0;

    /* Average the last 3 real values */
    sum = 0.0f;
    for (i = 0; i < FILTER_SIZE; i++)
        sum += rpm_buffer[i];

    rpm_filtered = sum / FILTER_SIZE;
    return rpm_filtered;
}

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
	    if (htim->Instance == TIM2)
    {
        if (first_capture == 0)
        {

            capture1      = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
            first_capture = 1;
        }
        else
        {
            capture2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
            if (capture2 >= capture1)
                difference = capture2 - capture1;
            else
                difference = (0xFFFFFFFF - capture1) + capture2 + 1;


            if (difference < 666)
            {
                first_capture = 0;
                return;
            }

            if (difference != 0)
            {
                frequency  = TIM2_CLK / (float)difference;
                motor_rpm  = frequency * multiplicator;


                if (motor_rpm > MAX_RPM)
                    motor_rpm = MAX_RPM;
                rpm_filtered = RPM_Filter(motor_rpm);
            }

            print_counter++;
            data_ready = 1;   /* tell main loop new data is available */
            first_capture = 0;
        }
    }


    last_capture_time = HAL_GetTick();
}
void syst_initialization(void)
{
HAL_Init();

SystemClock_Config();

MX_GPIO_Init();
MX_TIM8_Init();
MX_USART2_UART_Init();
MX_COMP1_Init();
MX_TIM2_Init();
MX_TIM5_Init();
MX_TIM3_Init();
MX_DAC1_Init();

/* USER CODE BEGIN 2 */
HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_1);
HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_2);
HAL_TIM_PWM_Start(&htim8, TIM_CHANNEL_3);
HAL_TIM_Base_Start_IT(&htim8);

HAL_DAC_Start(&hdac1, DAC_CHANNEL_1);
HAL_DAC_SetValue(&hdac1, DAC_CHANNEL_1, DAC_ALIGN_12B_R, 1985);

HAL_COMP_Start(&hcomp1);
/* USER CODE END 2 */
HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
/* Infinite loop */
HAL_TIM_PWM_Start(&htim5, TIM_CHANNEL_1);
HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);
__HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, 6666);
HAL_TIM_IC_Start_IT(&htim2, TIM_CHANNEL_1);


HAL_NVIC_SetPriority(TIM8_UP_IRQn,    0, 0);
HAL_NVIC_SetPriority(TIM2_IRQn,       2, 0);
HAL_NVIC_SetPriority(USART2_IRQn,     3, 0);


}
float PI_Controller(float ref, float measured, float dt)
{
    /* error = how far we are from the target
       if ref=500 and motor=300, error=200 RPM */
    float error = ref - measured;

    /* P part: instant reaction proportional to error
       big error = big correction
       small error = small correction */
    float P = Kp * error;

    /* I part: memory of past errors
       accumulates over time until error reaches zero
       dt = time in seconds since last call, keeps units correct */
    integral += Ki * error * dt;

    /* Anti-windup: if integral grows too big it causes overshoot
       clamp it to a safe range in RPM units */
    if (integral >  50.0f) integral =  50.0f;
    if (integral < -50.0f) integral = -50.0f;

    /* Final output = P + I combined */
    return P + integral;
}
/* USER CODE END 4 */
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{

  __disable_irq();
  while (1)
  {
  }

}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
