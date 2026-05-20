<script lang="ts">
import { Progress as ProgressPrimitive } from 'bits-ui';
import { cn, type WithoutChildrenOrChild } from '$lib/utils';

type Props = WithoutChildrenOrChild<ProgressPrimitive.RootProps>;
let { class: className, value, max = 100, ref = $bindable(null), ...rest }: Props = $props();
</script>

<ProgressPrimitive.Root
  bind:ref
  class={cn('bg-surface2 relative h-1.5 w-full overflow-hidden rounded-full', className)}
  {...rest}
>
  <div
    class="bg-primary h-full w-full flex-1 transition-all"
    style:transform="translateX(-{100 - (100 * (value ?? 0)) / (max ?? 100)}%)"
  ></div>
</ProgressPrimitive.Root>
