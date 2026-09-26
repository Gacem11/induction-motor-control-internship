/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "comp.h"
#include "dac.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "control.h"
#include "speed.h"
#include <stdio.h>
#include <stdlib.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
float PI_Controller(float ref, float measured, float dt);
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */

/* ---- Closed-loop tuning & command interface (driven from the PC GUI) ---- */
static volatile float ref_speed_cmd = 500.0f;   // RPM reference, settable from GUI
static volatile float Kp_gain       = 0.01f;     // speed-loop P gain, settable from GUI
static volatile float Ki_gain       = 0.01f;     // speed-loop I gain, settable from GUI

/* ---- Rotor flux observer (d-axis current model) ---- */
/* Matches identified motor parameters */
#define MOTOR_LM   0.31f                   // mutual inductance [H]
#define MOTOR_RR   1.92f                   // rotor resistance [Ohm]
#define MOTOR_LR   0.32106f                // rotor self-inductance [H] (Lm + Llr)
#define MOTOR_TR   (MOTOR_LR / MOTOR_RR)   // rotor time constant [s]
static volatile float psi_r_est = 0.0f;    // estimated rotor flux magnitude [Wb]

/* ---- UART command reception (simple ASCII line protocol) ---- */
#define RX_BUF_LEN 32
static uint8_t  rx_byte;
static char     rx_line[RX_BUF_LEN];
static uint8_t  rx_idx = 0;
static volatile uint8_t line_ready = 0;

/* ---- Provided by control.c ---- */
extern volatile float i_dq_d;
extern volatile float i_dq_q;
extern volatile float refrence_torque;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_ADC1_Init();
  MX_TIM3_Init();
  MX_USART2_UART_Init();
  MX_COMP4_Init();
  MX_DAC1_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */

  Control_Init(&hadc1,&htim3);
  HAL_COMP_Start(&hcomp4);
  Speed_Init(&hdac1, &htim2);
  HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
  HAL_Delay(1000);
  char msg[] = "Started\r\n";
  HAL_UART_Transmit(&huart2, (uint8_t*)msg, sizeof(msg)-1, 1000);

  float dt = 0.0005f;   // matches control.c's decimated data_ready rate (2kHz)

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

    if (line_ready)
    {
        line_ready = 0;
        float val = atof(&rx_line[1]);
        switch (rx_line[0])
        {
            case 'S': ref_speed_cmd = val; break;
            case 'P': Kp_gain       = val; break;
            case 'I': Ki_gain       = val; break;
            default: break;
        }
    }

    if(data_ready == 1)
    {
        data_ready = 0;
        int v1 = (int)(i_meas_1 * 1000);
        int v2 = (int)(i_meas_2 * 1000);
        int v3 = (int)(i_meas_3 * 1000);
        int vr = (int)(i_ref_1  * 1000);
        int idv = (int)(i_dq_d  * 1000);
        int iqv = (int)(i_dq_q  * 1000);
        int rpm = (int)rpm_filtered;
        Speed_CheckTimeout();
        refrence_torque = PI_Controller(ref_speed_cmd, rpm_filtered, dt);

        psi_r_est += dt * ((MOTOR_LM / MOTOR_TR) * i_dq_d - psi_r_est / MOTOR_TR);

        int fluxv = (int)(psi_r_est * 1000);

        char buf[100];
        int len = sprintf(buf,
                "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\r\n",
                v1, v2, v3, vr, idv, iqv, fluxv, sw1, sw2, sw3, rpm);
        HAL_UART_Transmit(&huart2, (uint8_t*)buf, len, 1000);
    }
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
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
float PI_Controller(float ref, float measured, float dt)
{
    static float integral = 0.0f;
    const float TORQUE_MAX =  14.5f;
    const float TORQUE_MIN = -14.5f;

    float error = ref - measured;
    float P = Kp_gain * error;
    integral += Ki_gain * error * dt;

    if (integral > TORQUE_MAX) integral = TORQUE_MAX;
    if (integral < TORQUE_MIN) integral = TORQUE_MIN;

    float output = P + integral;
    if (output > TORQUE_MAX) output = TORQUE_MAX;
    if (output < TORQUE_MIN) output = TORQUE_MIN;
    return output;
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART2) return;

    if (rx_byte == '\n' || rx_byte == '\r')
    {
        rx_line[rx_idx] = '\0';
        if (rx_idx > 0) line_ready = 1;
        rx_idx = 0;
    }
    else if (rx_idx < RX_BUF_LEN - 1)
    {
        rx_line[rx_idx++] = (char)rx_byte;
    }
    HAL_UART_Receive_IT(&huart2, &rx_byte, 1);   // re-arm for next byte
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
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
