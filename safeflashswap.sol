// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./IERC20.sol";
import "./SafeERC20.sol";
import "./ReentrancyGuard.sol";

interface ISwapRouter02 {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
        uint256 deadline;
    }

    function exactInputSingle(
        ExactInputSingleParams calldata params
    ) external payable returns (uint256 amountOut);
}

interface IUniswapV3Pool {
    function swap(
        address recipient,
        bool zeroForOne,
        int256 amountSpecified,
        uint160 sqrtPriceLimitX96,
        bytes calldata data
    ) external returns (int256 amount0, int256 amount1);
}

contract SafeFlashSwap is ReentrancyGuard {
    using SafeERC20 for IERC20;

    address private constant ROUTER =
        0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E;

    uint160 private constant MIN_SQRT_RATIO = 4295128739;
    uint160 private constant MAX_SQRT_RATIO =
        1461446703485210103287273052203988822378723970342;

    error InvalidAddress();
    error InvalidAmount();
    error InvalidCallback();
    error NoProfit();

    function flashSwap(
        address pool0,
        uint24 fee1,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 deadline
    ) external nonReentrant {
        if (pool0 == address(0) || tokenIn == address(0) || tokenOut == address(0))
            revert InvalidAddress();
        if (amountIn == 0) revert InvalidAmount();

        bool zeroForOne = tokenIn < tokenOut;
        uint160 sqrtPriceLimitX96 = zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1;

        bytes memory data = abi.encode(
            msg.sender,
            pool0,
            fee1,
            tokenIn,
            tokenOut,
            amountIn,
            zeroForOne,
            deadline
        );

        IUniswapV3Pool(pool0).swap(
            address(this),
            zeroForOne,
            int256(amountIn),
            sqrtPriceLimitX96,
            data
        );
    }

    function _swap(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline
    ) private returns (uint256 amountOut) {
        IERC20(tokenIn).safeApprove(ROUTER, 0);
        IERC20(tokenIn).safeApprove(ROUTER, amountIn);

        ISwapRouter02.ExactInputSingleParams memory params =
            ISwapRouter02.ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: fee,
                recipient: address(this),
                amountIn: amountIn,
                amountOutMinimum: amountOutMin,
                sqrtPriceLimitX96: 0,
                deadline: deadline
            });

        amountOut = ISwapRouter02(ROUTER).exactInputSingle(params);
    }

    function uniswapV3SwapCallback(
        int256 amount0,
        int256 amount1,
        bytes calldata data
    ) external nonReentrant {
        (
            address caller,
            address pool0,
            uint24 fee1,
            address tokenIn,
            address tokenOut,
            uint256 amountIn,
            bool zeroForOne,
            uint256 deadline
        ) = abi.decode(data, (address,address,uint24,address,address,uint256,bool,uint256));

        if (msg.sender != pool0) revert InvalidCallback();

        uint256 amountOut = zeroForOne ? uint256(-amount1) : uint256(-amount0);

        // Checks-Effects-Interactions
        uint256 buyBackAmount = _swap(tokenOut, tokenIn, fee1, amountOut, amountIn, deadline);

        if (buyBackAmount < amountIn) revert NoProfit();
        uint256 profit = buyBackAmount - amountIn;

        // Repay pool first
        IERC20(tokenIn).safeTransfer(pool0, amountIn);

        // Then send profit to caller
        if (profit > 0) {
            IERC20(tokenIn).safeTransfer(caller, profit);
        }
    }
}
